"""PhaseManager — assigns a focused task for the upcoming phase."""

from __future__ import annotations

import logging

from pr_auto_reviewer.application.ports.inbound.brief_next_phase_use_case import (
    BriefNextPhaseUseCase,
)
from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.application.ports.outbound.command_bus_port import (
    CommandBusPort,
)
from pr_auto_reviewer.domain.entities.manager_agent import ManagerAgent
from pr_auto_reviewer.domain.messages.events.agent_exchange_event import (
    AgentExchangeEvent,
)
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.review_phase import ReviewPhase
from pr_auto_reviewer.domain.value_objects.sub_agent_role import SubAgentRole
from pr_auto_reviewer.infrastructure.templates.conversation_renderers import (
    ManagerBriefSystemRenderer,
    ManagerBriefUserRenderer,
)

logger = logging.getLogger(__name__)


class PhaseManager(BriefNextPhaseUseCase):
    """Refine the next phase's task between phases, as the manager role documents.

    The manager acts at the start of the review and between phases: it
    reads what the completed phases produced and hands the next phase a
    focused task so a phase never re-reviews findings another phase
    owns. An unavailable or empty manager reply yields an empty brief so
    the review proceeds unchanged.
    """

    def __init__(
        self,
        chat_port: AgentChatPort,
        command_bus: CommandBusPort | None = None,
    ) -> None:
        self._chat_port = chat_port
        self._command_bus = command_bus
        self._brief_system = ManagerBriefSystemRenderer()
        self._brief_user = ManagerBriefUserRenderer()

    def brief(
        self,
        next_phase: ReviewPhase,
        findings_summary: str,
        review_session: str,
        pr_identifier: str = "",
    ) -> str:
        """Return the assignment text for *next_phase*, or empty when none."""
        messages = self._build_messages(next_phase, findings_summary)
        try:
            raw = self._chat_port.send(messages)
        except Exception:
            logger.warning(
                "Manager briefing failed for phase %s; continuing without",
                next_phase.phase_name,
                exc_info=True,
            )
            return ""
        brief = (raw or "").strip()
        if not brief:
            return ""
        self._publish_exchange(
            next_phase, pr_identifier, review_session, messages, raw,
        )
        logger.info(
            "Manager briefed phase %s between phases", next_phase.phase_name,
        )
        return brief

    def _publish_exchange(
        self,
        next_phase: ReviewPhase,
        pr_identifier: str,
        review_session: str,
        messages: list[ConversationMessage],
        raw_reply: str,
    ) -> None:
        """Emit the finished briefing exchange for the transcript log."""
        if self._command_bus is None:
            return
        transcript = [
            *messages,
            ConversationMessage(role="assistant", content=raw_reply),
        ]
        self._command_bus.dispatch(AgentExchangeEvent(
            role=SubAgentRole.MANAGER,
            phase_name=next_phase.phase_name,
            pr_identifier=pr_identifier,
            review_session=review_session,
            messages=transcript,
        ))

    def _build_messages(
        self, next_phase: ReviewPhase, findings_summary: str,
    ) -> list[ConversationMessage]:
        """Compose the manager's between-phases assignment prompt."""
        peer = next_phase.role
        role_text = ""
        if peer is not None:
            role_text = (
                f"Upcoming phase peer: {peer.role}.\n"
                f"Responsibility: {peer.responsibility}\n"
                f"Behavior: {peer.behavior}"
            )
        return [
            self._brief_system.render(manager=ManagerAgent()),
            self._brief_user.render(
                role_text=role_text,
                phase_name=next_phase.phase_name,
                phase_instructions=next_phase.system_prompt[:400],
                findings_summary=findings_summary or "(none)",
            ),
        ]