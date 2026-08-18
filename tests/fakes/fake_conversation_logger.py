"""Fake MarkdownConversationLogger for tests."""

from __future__ import annotations

from pathlib import Path

from pr_auto_reviewer.application.ports.outbound.conversation_logger_port import (
    ConversationLoggerPort,
)


class FakeMarkdownConversationLogger(ConversationLoggerPort):
    """Fake conversation logger that tracks calls without writing to disk."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else Path("/tmp/fake-conversations")
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self.log_conversation_calls: list[tuple[str, str, list, dict]] = []

    def log_conversation(
        self,
        phase_name: str,
        pr_identifier: str,
        messages: list[Any],
        metadata: dict[str, Any],
    ) -> Path:
        """Track call without writing to disk."""
        self.log_conversation_calls.append((phase_name, pr_identifier, messages, metadata))
        # Return a fake path
        safe_pr = pr_identifier.replace("/", "_").replace("#", "_")
        phase_dir = self._base_dir / safe_pr
        phase_dir.mkdir(parents=True, exist_ok=True)
        return phase_dir / f"fake_{phase_name}_{len(self.log_conversation_calls)}.md"