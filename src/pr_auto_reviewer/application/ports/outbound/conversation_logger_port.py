"""ConversationLoggerPort — outbound port for persisting agent conversations."""

from pathlib import Path
from typing import Any, Protocol


class TranscriptMetadata:
    """The metadata keys every conversation logger understands.

    Event publishers and the logger share these spellings, so a key
    is declared once on the port contract instead of repeated as
    string literals across layers.
    """

    AGENT_ROLE = "agent_role"
    VERDICT = "verdict"
    ITEM_COUNT = "item_count"
    SKIPPED = "skipped"
    GRADE = "grade"
    FEEDBACK = "feedback"


class ConversationLoggerPort(Protocol):

    def log_conversation(
        self,
        phase_name: str,
        pr_identifier: str,
        messages: list[Any],
        metadata: dict[str, Any],
        review_session: str,
    ) -> Path:
        """Append *messages* to a phase-topic transcript and return its path.

        Args:
            phase_name: Human-readable phase label (e.g. "Bug Hunt — Diff").
            pr_identifier: Scoped PR key (e.g. ``"gbrennon/tmux-worktrees#63"``).
            messages: The full ``ConversationMessage`` list from the agent loop.
            metadata: Extra context (model, turn count, verdict, item count).
            review_session: Review-run key (start timestamp) grouping
                transcripts into a per-run subdirectory.

        Returns:
            Absolute path to the transcript file.
        """
        ...
