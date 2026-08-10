"""MarkdownConversationLogger — persist agent conversations as readable markdown."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar

from pr_auto_reviewer.application.ports.outbound.conversation_logger_port import (
    ConversationLoggerPort,
)

logger = logging.getLogger(__name__)


class MarkdownConversationLogger(ConversationLoggerPort):
    """Write multi-turn agent conversations to timestamped markdown files.

    Each log shows the agent role, what was sent to the LLM, and what
    answer was received — turn by turn.
    """

    _PHASE_TO_ROLE: ClassVar[dict[str, str]] = {
        "Bug Hunt — Diff": "engineer",
        "Bug Hunt — Branch": "explorer",
        "Architecture Review": "architect",
    }

    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            base_dir = Path.home() / ".cache" / "pr-auto-reviewer" / "conversations"
        self._base_dir = Path(base_dir)

    def log_conversation(
        self,
        phase_name: str,
        pr_identifier: str,
        messages: list[Any],
        metadata: dict[str, Any],
    ) -> Path:
        safe_pr = pr_identifier.replace("/", "_").replace("#", "_")
        phase_dir = self._base_dir / safe_pr
        phase_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_phase = phase_name.replace(" ", "_").replace("—", "-").lower()
        file_path = phase_dir / f"{safe_phase}_{timestamp}.md"

        agent_role = self._PHASE_TO_ROLE.get(
            phase_name, metadata.get("agent_role", "unknown")
        )

        lines: list[str] = []
        lines.append(f"# Agent: {agent_role}")
        lines.append(f"# Phase: {phase_name}")
        lines.append(f"# PR: {pr_identifier}")
        lines.append(f"# Model: {metadata.get('model', 'unknown')}")
        lines.append(
            f"# Turns: {metadata.get('turns', 0)}"
            f" | Verdict: {metadata.get('verdict', 'unknown')}"
            f" | Items: {metadata.get('item_count', 0)}"
        )
        lines.append(f"# {timestamp}")
        lines.append("")

        turn_number = 0
        for msg in messages:
            role = getattr(msg, "role", "unknown")
            content = getattr(msg, "content", "")
            tool_call = getattr(msg, "tool_call", None)
            tool_result = getattr(msg, "tool_result", None)

            if role == "system":
                turn_number += 1
                lines.append("---")
                lines.append("")
                lines.append(f"## Turn {turn_number}")
                lines.append("")
                lines.append(f"### Sent — System Prompt ({agent_role})")
                lines.append("")
                if len(content) > 4000:
                    content = content[:4000] + "\n\n... (truncated)"
                lines.append(content)
                lines.append("")
                continue

            if role == "user" and tool_result is not None:
                tr_status = getattr(tool_result, "status", "unknown")
                tr_data = getattr(tool_result, "data", None)
                tr_error = getattr(tool_result, "error", None)
                lines.append(f"### Received — Tool Result (`{tr_status}`)")
                if tr_data is not None:
                    data_str = json.dumps(tr_data, indent=2, default=str)
                    if len(data_str) > 2000:
                        data_str = data_str[:2000] + "\n... (truncated)"
                    lines.append("")
                    lines.append("```json")
                    lines.append(data_str)
                    lines.append("```")
                if tr_error:
                    lines.append(f"**Error:** {tr_error}")
                lines.append("")
                continue

            if role == "user":
                lines.append("### Sent — Context")
                lines.append("")
                if len(content) > 2000:
                    content = content[:2000] + "\n\n... (truncated)"
                lines.append(content)
                lines.append("")
                continue

            if role == "assistant":
                if tool_call is not None:
                    tc_name = getattr(tool_call, "tool_name", "unknown")
                    tc_args = getattr(tool_call, "arguments", {})
                    lines.append(f"### Received — Tool Call (`{tc_name}`)")
                    lines.append("")
                    lines.append("```json")
                    lines.append(json.dumps(tc_args, indent=2, default=str))
                    lines.append("```")
                else:
                    lines.append(f"### Received — Answer ({agent_role})")
                    lines.append("")
                    if len(content) > 4000:
                        content = content[:4000] + "\n\n... (truncated)"
                    lines.append(content)
                lines.append("")
                continue

        file_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Conversation logged to %s", file_path)
        return file_path
