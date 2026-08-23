"""PhaseAdvisor — grades a finished peer phase on the S/B/D/F scale."""

from __future__ import annotations

import json
import logging
import re

from pr_auto_reviewer.application.ports.inbound.assess_phase_use_case import (
    AssessPhaseUseCase,
)
from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.domain.entities.advisor_agent import AdvisorAgent
from pr_auto_reviewer.domain.value_objects.advisor_directive import (
    AdvisorDirective,
)
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.review_phase import ReviewPhase
from pr_auto_reviewer.domain.value_objects.sub_agent_grade import (
    SubAgentGrade,
)

logger = logging.getLogger(__name__)


class PhaseAdvisor(AssessPhaseUseCase):
    """Grade a finished phase the way the advisor role is documented.

    The advisor does not review code itself: it watches what the peer
    sub-agent produced during *phase*, grades it against the task the
    manager assigned (S: impressive, B: okok, D: whatever, F: don't do
    this!), and on an F returns an improved prompt that re-explains the
    task so the phase can be restarted. A missing or unparseable advisor
    reply resolves to ``OKOK`` so a grading failure never halts the
    review.
    """

    _GRADE_KEYS = ("grade", "verdict", "assessment")
    _FEEDBACK_KEYS = ("feedback", "reason", "interjection")
    _PROMPT_KEYS = ("improved_prompt", "improvedPrompt", "reprompt")

    def __init__(self, chat_port: AgentChatPort) -> None:
        self._chat_port = chat_port

    def assess(
        self,
        phase: ReviewPhase,
        assignment: str,
        phase_result: PhaseResult,
    ) -> AdvisorDirective:
        """Return the advisor's directive for the finished *phase*."""
        peer = phase.role
        try:
            raw = self._chat_port.send(self._build_messages(
                phase, assignment, phase_result,
            ))
        except Exception:
            logger.warning(
                "Advisor grading failed for phase %s; accepting output",
                phase.phase_name,
                exc_info=True,
            )
            return AdvisorDirective(grade=SubAgentGrade.OKOK)
        directive = self._parse_directive(raw)
        if peer is not None and directive.blocks_output:
            logger.info(
                "Advisor graded phase %s as F (don't do this!); blocking "
                "output and restarting with improved prompt",
                phase.phase_name,
            )
        return directive

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
        advisor = AdvisorAgent()
        findings = "\n".join(
            f"- {item.file_path or '?'}: {item.description}"
            for item in phase_result.items
        ) or "(no findings reported)"
        system = (
            f"{advisor.description}\n\n"
            f"{advisor.interaction}\n\n"
            "You grade the FINISHED phase, never the diff. Use exactly one "
            "of the four grades and output a single JSON object with keys "
            '"grade", "feedback", and "improved_prompt".'
        )
        user = (
            f"{self._assigned_task(phase, assignment)}\n\n"
            f"Phase: {phase.phase_name}\n"
            f"Phase verdict: {phase_result.llm_verdict or 'none'}\n"
            f"Phase reason: {phase_result.llm_reason or ''}\n"
            f"Findings reported:\n{findings}\n\n"
            'Respond with JSON: {"grade": "impressive|okok|whatever|'
            'don\'t do this!", "feedback": "short note to the peer", '
            '"improved_prompt": "ONLY when grade is don\'t do this!: an '
            'improved version of the original prompt re-explaining the '
            'task; otherwise empty string"}'
        )
        return [
            ConversationMessage(role="system", content=system),
            ConversationMessage(role="user", content=user),
        ]

    @classmethod
    def _parse_directive(cls, raw: str) -> AdvisorDirective:
        """Parse an advisor JSON reply into a directive, tolerantly."""
        if not raw or not raw.strip():
            return AdvisorDirective(grade=SubAgentGrade.OKOK)
        cleaned = raw.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
        if fence:
            cleaned = fence.group(1).strip()
        try:
            payload = json.loads(cleaned)
            if not isinstance(payload, dict):
                return AdvisorDirective(grade=SubAgentGrade.OKOK)
        except json.JSONDecodeError:
            logger.debug(
                "Advisor reply was not JSON; accepting phase output"
            )
            return AdvisorDirective(grade=SubAgentGrade.OKOK)

        grade_text = cls._first_value(
            payload, cls._GRADE_KEYS
        ) or "okok"
        feedback = cls._first_value(payload, cls._FEEDBACK_KEYS) or ""
        improved = cls._first_value(payload, cls._PROMPT_KEYS) or ""
        return AdvisorDirective(
            grade=SubAgentGrade.from_phrase(str(grade_text)),
            feedback=str(feedback),
            improved_prompt=str(improved),
        )

    @staticmethod
    def _first_value(payload: dict, keys: tuple[str, ...]) -> str | None:
        """Return the first present string value among *keys*."""
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None