"""PhaseAdvisorService — grades a finished peer phase on the S/A/B/C/D/F scale."""

from __future__ import annotations

import dataclasses
import json
import logging
import re

from pr_auto_reviewer.application.ports.inbound.assess_phase_port import (
    AssessPhasePort,
)
from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.application.ports.outbound.command_bus_port import (
    CommandBusPort,
)
from pr_auto_reviewer.domain.exceptions.llm_response_malformed_error import (
    LlmResponseMalformedError,
)
from pr_auto_reviewer.application.ports.outbound.conversation_logger_port import (
    TranscriptMetadata,
)
from pr_auto_reviewer.domain.entities.advisor_agent import AdvisorAgent
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.messages.events.agent_exchange_event import (
    AgentExchangeEvent,
)
from pr_auto_reviewer.domain.value_objects.advisor_directive import (
    AdvisorDirective,
)
from pr_auto_reviewer.domain.value_objects.advisor_turn_evidence import (
    AdvisorTurnEvidence,
)
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.conversation_purpose import (
    ConversationPurpose,
)
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.review_phase import ReviewPhase
from pr_auto_reviewer.domain.value_objects.sub_agent_grade import (
    SubAgentGrade,
)
from pr_auto_reviewer.domain.value_objects.sub_agent_role import SubAgentRole
from pr_auto_reviewer.infrastructure.templates.conversation_renderers import (
    AdvisorPhaseGradeSystemRenderer,
    AdvisorPhaseGradeUserRenderer,
    AdvisorTurnGradeSystemRenderer,
    AdvisorTurnGradeUserRenderer,
)

logger = logging.getLogger(__name__)


class PhaseAdvisorService(AssessPhasePort):
    """Grade a finished phase and each live turn the way the advisor role documents.

    The advisor does not review code itself: it watches what the peer
    sub-agent produces during *phase*, grades it against the task the
    manager assigned (S: impressive, A: amazing, B: okok, C: acceptable,
    D: whatever, F: don't do this!), and on an F reports the blocker to
    the manager, who re-plans the task before the phase restarts. A
    missing or unparseable advisor reply resolves to ``OKOK`` so a
    non-fatal grading failure never halts the review.
    """

    _GRADE_KEYS = ("grade",)
    _FEEDBACK_KEYS = ("feedback",)
    _PROMPT_KEYS = ("improved_prompt", "improvedPrompt", "reprompt")

    def __init__(
        self,
        chat_port: AgentChatPort,
        command_bus: CommandBusPort | None = None,
    ) -> None:
        self._chat_port = chat_port
        self._command_bus = command_bus
        self._turn_system = AdvisorTurnGradeSystemRenderer()
        self._turn_user = AdvisorTurnGradeUserRenderer()
        self._phase_system = AdvisorPhaseGradeSystemRenderer()
        self._phase_user = AdvisorPhaseGradeUserRenderer()

    def assess(
        self,
        phase: ReviewPhase,
        assignment: str,
        phase_result: PhaseResult,
        review_session: str,
        pr_identifier_service: str = "",
    ) -> AdvisorDirective:
        """Return the advisor's directive for the finished *phase*."""
        peer = phase.role
        messages = self._build_messages(phase, assignment, phase_result)
        try:
            raw = self._chat_port.send(
                messages,
                purpose=ConversationPurpose.ADVISOR_PHASE,
                session_id=review_session,
            )
        except LlmUnavailableError:
            raise
        except Exception:
            logger.warning(
                "Advisor grading failed for phase %s",
                phase.phase_name,
                exc_info=True,
            )
            raise
        directive = self._cap_unevidenced_grade(
            self._parse_directive(raw), phase_result,
        )
        self._publish_exchange(
            phase.phase_name, pr_identifier_service, review_session, messages, raw,
            directive,
        )
        if peer is not None and directive.blocks_output:
            logger.info(
                "Advisor graded phase %s as F (don't do this!); blocking "
                "output and handing the blocker to the manager",
                phase.phase_name,
            )
        return directive

    def observe(
        self,
        evidence: AdvisorTurnEvidence,
        review_session: str,
        pr_identifier_service: str = "",
    ) -> AdvisorDirective:
        """Grade one structured peer turn without receiving raw output."""
        messages = self._build_turn_messages(evidence)
        try:
            raw = self._chat_port.send(
                messages,
                purpose=ConversationPurpose.ADVISOR_TURN,
                session_id=review_session,
            )
        except LlmUnavailableError:
            raise
        except Exception:
            logger.warning(
                "Advisor turn observation failed for %s",
                evidence.phase_name,
                exc_info=True,
            )
            raise
        directive = self._parse_directive(raw)
        self._publish_exchange(
            evidence.phase_name,
            pr_identifier_service,
            review_session,
            messages,
            raw,
            directive,
        )
        return directive

    def _build_turn_messages(
        self, evidence: AdvisorTurnEvidence,
    ) -> list[ConversationMessage]:
        """Compose a per-turn grading prompt from structured evidence."""
        return [
            self._turn_system.render(advisor=AdvisorAgent()),
            self._turn_user.render(
                phase_name=evidence.phase_name,
                turn_kind=evidence.turn_kind.value,
                tool_name=evidence.tool_name,
                tool_path=evidence.tool_path,
                claim_count=evidence.claim_count,
            ),
        ]

    def _publish_exchange(
        self,
        phase_name: str,
        pr_identifier_service: str,
        review_session: str,
        messages: list[ConversationMessage],
        raw_reply: str,
        directive: AdvisorDirective,
    ) -> None:
        """Emit the finished grading exchange for the transcript log."""
        if self._command_bus is None:
            return
        transcript = [
            *messages,
            ConversationMessage(role="assistant", content=raw_reply),
        ]
        self._command_bus.dispatch(AgentExchangeEvent(
            role=SubAgentRole.ADVISOR,
            phase_name=phase_name,
            pr_identifier_service=pr_identifier_service,
            review_session=review_session,
            messages=transcript,
            metadata={
                TranscriptMetadata.GRADE: str(directive.grade),
                TranscriptMetadata.FEEDBACK: directive.feedback,
            },
        ))

    def _assigned_task(self, phase: ReviewPhase, assignment: str) -> str:
        """Render the task the manager assigned plus the peer's role contract."""
        peer = phase.role
        role_text = ""
        if peer is not None:
            role_text = (
                f"Peer role: {peer.role}.\n"
                f"Responsibility: {peer.responsibility}\n"
                f"Behavior: {peer.behavior}\n"
                f"Interaction: {peer.interaction}"
            )
        assignment_text = assignment.strip() or "(no explicit assignment)"
        return (
            f"The task the manager assigned:\n{assignment_text}\n\n"
            f"{role_text}"
        ).strip()

    def _build_messages(
        self,
        phase: ReviewPhase,
        assignment: str,
        phase_result: PhaseResult,
    ) -> list[ConversationMessage]:
        """Compose the advisor's grading prompt from the phase outcome."""
        findings = "\n".join(
            f"- {item.file_path or '?'}: {item.description}"
            for item in phase_result.items
        ) or "(no findings reported)"
        return [
            self._phase_system.render(advisor=AdvisorAgent()),
            self._phase_user.render(
                assigned_task=self._assigned_task(phase, assignment),
                phase_name=phase.phase_name,
                phase_verdict=phase_result.llm_verdict or "none",
                phase_reason=phase_result.llm_reason or "",
                findings=findings,
                tool_evidence=PhaseAdvisorService._format_tool_evidence(phase_result),
            ),
        ]

    @staticmethod
    def _format_tool_evidence(phase_result: PhaseResult) -> str:
        """Format tool-use evidence as a concise summary string."""
        return (
            f"turns: {phase_result.turn_count}, "
            f"read_file: {phase_result.read_file_calls}, "
            f"run_snippet: {phase_result.run_snippet_calls}"
        )

    @staticmethod
    def _cap_unevidenced_grade(
        directive: AdvisorDirective, phase_result: PhaseResult,
    ) -> AdvisorDirective:
        """Demote S/A grades that lack ``run_snippet`` evidence.

        The advisor cannot see tool execution; an LLM can rationalize
        past the anti-praise prose clause and award IMPRESSIVE for a
        fabricated finding.  This mechanical cap enforces that a top
        grade with zero ``run_snippet`` calls is recorded as OKOK —
        both in the returned directive and in the published transcript.
        """
        grade = directive.grade
        if grade not in (SubAgentGrade.IMPRESSIVE, SubAgentGrade.AMAZING):
            return directive
        if phase_result.run_snippet_calls > 0:
            return directive
        logger.info(
            "Publish-grade cap: demoting %s → okok "
            "(zero run_snippet calls; %d read_file calls)",
            grade.value,
            phase_result.read_file_calls,
        )
        return dataclasses.replace(directive, grade=SubAgentGrade.OKOK)

    @classmethod
    def _parse_directive(cls, raw: str) -> AdvisorDirective:
        """Parse an advisor JSON reply into a validated directive."""
        if not isinstance(raw, str) or not raw.strip():
            raise LlmResponseMalformedError(str(raw))
        cleaned = raw.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
        if fence:
            cleaned = fence.group(1).strip()
        try:
            payload = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError) as exc:
            raise LlmResponseMalformedError(raw) from exc
        if not isinstance(payload, dict):
            raise LlmResponseMalformedError(raw)
        grade_text = cls._first_value(payload, cls._GRADE_KEYS)
        if grade_text is None:
            raise LlmResponseMalformedError(raw)
        feedback = cls._first_value(payload, cls._FEEDBACK_KEYS) or ""
        improved = cls._first_value(payload, cls._PROMPT_KEYS) or ""
        return AdvisorDirective(
            grade=SubAgentGrade.from_phrase(grade_text),
            feedback=feedback,
            improved_prompt=improved,
        )

    @staticmethod
    def _first_value(payload: dict, keys: tuple[str, ...]) -> str | None:
        """Return the first present string value among *keys*."""
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None
