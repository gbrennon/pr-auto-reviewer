"""ConversationLoggerPort — outbound port for persisting agent conversations."""

from pathlib import Path
from typing import Any, Protocol


class ConversationLoggerPort(Protocol):
    """Persist a multi-turn agent conversation to disk for inspection."""

    def log_conversation(
        self,
        phase_name: str,
        pr_identifier: str,
        messages: list[Any],
        metadata: dict[str, Any],
    ) -> Path:
        """Write *messages* to a timestamped file and return its path.

        Args:
            phase_name: Human-readable phase label (e.g. "Bug Hunt — Diff").
            pr_identifier: Scoped PR key (e.g. ``"gbrennon/tmux-worktrees#23"``).
            messages: The full ``ConversationMessage`` list from the agent loop.
            metadata: Extra context (model, turn count, verdict, item count).

        Returns:
            Absolute path to the written log file.
        """
        ...
