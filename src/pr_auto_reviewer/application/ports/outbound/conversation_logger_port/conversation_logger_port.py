from ._shared import *


class ConversationLoggerPort(Protocol):

    def log_conversation(
        self,
        phase_name: str,
        pr_identifier_service: str,
        messages: list[Any],
        metadata: dict[str, Any],
        review_session: str,
    ) -> Path:
        """Append *messages* to a phase-topic transcript and return its path.

        Args:
            phase_name: Human-readable phase label (e.g. "Bug Hunt — Diff").
            pr_identifier_service: Scoped PR key (e.g. ``"gbrennon/tmux-worktrees#63"``).
            messages: The full ``ConversationMessage`` list from the agent loop.
            metadata: Extra context (model, turn count, verdict, item count).
            review_session: Review-run key (start timestamp) grouping
                transcripts into a per-run subdirectory.

        Returns:
            Absolute path to the transcript file.
        """

