"""MarkdownConversationLogger — persist agent conversations as readable markdown."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from pr_auto_reviewer.application.ports.outbound.conversation_logger_port import (
    ConversationLoggerPort,
    TranscriptMetadata,
)
from pr_auto_reviewer.domain.value_objects.sub_agent_role import SubAgentRole
from pr_auto_reviewer.infrastructure.config.app_paths import AppPaths
from pr_auto_reviewer.infrastructure.transcript_routing import PEER_PHASE_ROUTES

logger = logging.getLogger(__name__)


class MarkdownConversationLogger(ConversationLoggerPort):
    """Write agent conversations to one markdown transcript per topic.

    Transcripts are grouped under ``base/pr/<owner>_<repo>_<pr>`` and,
    when a ``review_session`` is supplied, further under a per-run
    subdirectory keyed by the value (the review start timestamp):

    ``base/pr/<owner>_<repo>_<pr>/<review_session>/<ordinal><topic>.md``

    Every conversation for a topic — peer attempts, advisor grades,
    manager re-plans — is appended to that topic's single file, so the
    sorted file names read in review order and each file reads in
    execution order with turn numbers continuing across restarts.
    """

    _ROLE_BY_PHASE: ClassVar[dict[str, SubAgentRole]] = {
        route.label: route.role for route in PEER_PHASE_ROUTES
    }

    _TOPIC_BY_PHASE: ClassVar[dict[str, str]] = {
        route.label: f"{position:02d}-{route.slug}"
        for position, route in enumerate(PEER_PHASE_ROUTES, start=1)
    }

    _MANAGER_ROLE: ClassVar[SubAgentRole] = SubAgentRole.MANAGER
    _VERIFIER_ROLE: ClassVar[SubAgentRole] = SubAgentRole.VERIFIER
    _ADVISOR_ROLE: ClassVar[SubAgentRole] = SubAgentRole.ADVISOR

    _UNIDENTIFIED_ROLE = "unknown"
    _UNKNOWN_VERDICT = "unknown"

    _PLANNING_TOPIC = "00-planning"
    _VERIFIER_TOPIC = "05-verifier"

    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            base_dir = AppPaths.state_dir() / "conversations"
        self._base_dir = Path(base_dir)

    def _topic_for(self, phase_name: str, metadata: dict[str, Any]) -> str:
        """Return the reading-order topic slug for *phase_name*.

        Manager exchanges plan the review and share the planning topic.
        Every other exchange sorts under the review phase it belongs
        to, so advisor turn grades sit beside their phase's own
        transcript instead of jumping ahead of later phases. Verifier
        exchanges run after all phases and own the final topic.
        Unknown phases sort last.
        """
        agent_role = metadata.get(TranscriptMetadata.AGENT_ROLE, "")
        if agent_role == self._MANAGER_ROLE:
            return self._PLANNING_TOPIC
        phase_topic = self._TOPIC_BY_PHASE.get(phase_name)
        if phase_topic is not None:
            return phase_topic
        if agent_role == self._VERIFIER_ROLE:
            return self._VERIFIER_TOPIC
        slug = phase_name.replace(" ", "_").replace("—", "-").lower()
        return f"99-{slug}"

    _TURN_HEADING: ClassVar[re.Pattern[str]] = re.compile(
        r"^## Turn (\d+)$", re.MULTILINE
    )

    def log_conversation(
        self,
        phase_name: str,
        pr_identifier_service: str,
        messages: list[Any],
        metadata: dict[str, Any],
        review_session: str,
    ) -> Path:
        safe_pr = pr_identifier_service.replace("/", "_").replace("#", "_")
        phase_dir = self._base_dir / safe_pr
        if review_session:
            phase_dir = phase_dir / review_session
        phase_dir.mkdir(parents=True, exist_ok=True)

        topic = self._topic_for(phase_name, metadata)
        file_path = phase_dir / f"{topic}.md"
        existing = file_path.read_text(encoding="utf-8") if file_path.exists() else ""

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        acting_role = str(metadata.get(TranscriptMetadata.AGENT_ROLE, ""))
        agent_role = (
            acting_role
            or self._ROLE_BY_PHASE.get(phase_name, self._UNIDENTIFIED_ROLE)
        )
        turn_offset = self._last_turn_number(existing)

        rendered, turn_count = self._render_messages(messages, agent_role, turn_offset)

        blocks: list[str] = []
        if existing:
            blocks.append(existing.rstrip("\n"))
        else:
            blocks.append(self._preamble(phase_name, pr_identifier_service, review_session))
        blocks.append("---")
        blocks.append(f"# {agent_role} — {timestamp}")
        blocks.append(self._summary_line(agent_role, metadata, turn_count))
        blocks.append(rendered)

        file_path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        logger.info("Conversation logged to %s", file_path)
        return file_path

    def _preamble(
        self, phase_name: str, pr_identifier_service: str, review_session: str
    ) -> str:
        """Return the header block written when a transcript is created."""
        lines = [
            f"# Phase: {phase_name}",
            f"# PR: {pr_identifier_service}",
        ]
        if review_session:
            lines.append(f"# Review: {review_session}")
        return "\n".join(lines)

    def _summary_line(
        self, agent_role: str, metadata: dict[str, Any], turn_count: int
    ) -> str:
        """Return the per-conversation summary line for the acting role.

        Peers produce review verdicts and findings. The advisor produces
        grades and feedback — never a verdict. The manager and verifier
        exchanges carry no outcome fields at all.
        """
        parts = [f"Turns: {turn_count}"]
        if agent_role == self._ADVISOR_ROLE:
            grade = metadata.get(TranscriptMetadata.GRADE, "")
            feedback = metadata.get(TranscriptMetadata.FEEDBACK, "")
            if grade:
                parts.append(f"Grade: {grade}")
            if feedback:
                parts.append(f"Feedback: {feedback}")
            return " | ".join(parts)
        if agent_role in (self._MANAGER_ROLE, self._VERIFIER_ROLE):
            return parts[0]
        parts.append(f"Verdict: {metadata.get(TranscriptMetadata.VERDICT, self._UNKNOWN_VERDICT)}")
        parts.append(self._items_part(metadata))
        return " | ".join(parts)

    def _items_part(self, metadata: dict[str, Any]) -> str:
        """Return the findings summary fragment for a conversation."""
        items_part = f"Items: {metadata.get(TranscriptMetadata.ITEM_COUNT, 0)}"
        skipped = metadata.get(TranscriptMetadata.SKIPPED, 0)
        if skipped:
            items_part += f" (Skipped: {skipped})"
        return items_part

    def _last_turn_number(self, existing: str) -> int:
        """Return the highest turn number already present in a transcript."""
        return max((int(m) for m in self._TURN_HEADING.findall(existing)), default=0)

    def _render_messages(
        self, messages: list[Any], agent_role: str, turn_offset: int
    ) -> tuple[str, int]:
        """Render messages as turn sections numbered from ``turn_offset``."""
        assistant_count = 0
        current_turn = 0
        lines: list[str] = []
        for msg in messages:
            role = getattr(msg, "role", "unknown")
            content = getattr(msg, "content", "")
            tool_call = getattr(msg, "tool_call", None)
            tool_result = getattr(msg, "tool_result", None)

            if role == "assistant":
                assistant_count += 1
                turn = assistant_count + turn_offset
            else:
                turn = (
                    assistant_count + turn_offset
                    if assistant_count > 0
                    else 1 + turn_offset
                )

            if turn != current_turn:
                if turn > 0:
                    lines.append("---")
                    lines.append("")
                    lines.append(f"## Turn {turn}")
                    lines.append("")
                current_turn = turn

            lines.extend(self._render_message(msg, role, content, tool_call, tool_result, agent_role))
        return "\n".join(lines), assistant_count

    def _render_message(
        self,
        msg: Any,
        role: str,
        content: str,
        tool_call: Any,
        tool_result: Any,
        agent_role: str,
    ) -> list[str]:
        """Render a single message's section lines."""
        if role == "system":
            return self._render_system(content, agent_role)
        if role == "user" and tool_result is not None:
            return self._render_tool_result(tool_result)
        if role == "user":
            return self._render_context(content)
        if role == "assistant":
            return self._render_assistant(content, tool_call, agent_role)
        return [content, ""]

    def _truncate(self, text: str, limit: int) -> str:
        """Return *text* clipped to *limit* characters with an ellipsis marker."""
        if len(text) > limit:
            return text[:limit] + "\n\n... (truncated)"
        return text

    def _render_system(self, content: str, agent_role: str) -> list[str]:
        """Render a system prompt section."""
        return [
            f"### Sent — System Prompt ({agent_role})",
            "",
            self._truncate(content, 4000),
            "",
        ]

    def _render_tool_result(self, tool_result: Any) -> list[str]:
        """Render a tool result section."""
        tr_status = getattr(tool_result, "status", "unknown")
        tr_data = getattr(tool_result, "data", None)
        tr_error = getattr(tool_result, "error", None)
        lines = [f"### Received — Tool Result (`{tr_status}`)"]
        if tr_data is not None:
            data_str = json.dumps(tr_data, indent=2, default=str)
            lines.extend(["", "```json", self._truncate(data_str, 2000), "```"])
        if tr_error:
            lines.append(f"**Error:** {tr_error}")
        lines.append("")
        return lines

    def _render_context(self, content: str) -> list[str]:
        """Render a user context section."""
        return ["### Sent — Context", "", self._truncate(content, 2000), ""]

    def _render_assistant(self, content: str, tool_call: Any, agent_role: str) -> list[str]:
        """Render an assistant tool-call or answer section."""
        if tool_call is not None:
            tc_name = getattr(tool_call, "tool_name", "unknown")
            tc_args = getattr(tool_call, "arguments", {})
            return [
                f"### Received — Tool Call (`{tc_name}`)",
                "",
                "```json",
                json.dumps(tc_args, indent=2, default=str),
                "```",
                "",
            ]
        return [
            f"### Received — Answer ({agent_role})",
            "",
            self._truncate(content, 4000),
            "",
        ]