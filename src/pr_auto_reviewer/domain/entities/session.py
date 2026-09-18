"""Session aggregate root for an agentic review conversation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ..exceptions.session_terminated_error import SessionTerminatedError
from ..services.context_compactor import ContextCompactor
from ..value_objects.compaction_result import CompactionResult
from ..value_objects.context_window import ContextWindow
from ..value_objects.conversation import Conversation
from ..value_objects.conversation_message import ConversationMessage
from ..value_objects.session_id import SessionId
from ..value_objects.session_status import SessionStatus
from ..value_objects.token_count import TokenCount
from ..value_objects.token_usage import TokenUsage


@dataclass(frozen=True)
class Session:
    """Immutable aggregate coordinating conversation and context state."""

    id: SessionId
    context_window: ContextWindow
    conversation: Conversation = field(default_factory=Conversation)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    status: SessionStatus = SessionStatus.INITIALIZED
    compaction_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(
        self,
        message: ConversationMessage,
        token_count: TokenCount | None = None,
    ) -> Session:
        """Append a message and advance current context consumption."""
        if self.status.is_terminal:
            raise SessionTerminatedError(
                f"Cannot add message to {self.status.value} session {self.id}"
            )

        tokens = token_count if token_count is not None else message.estimate_tokens()

        return replace(
            self,
            conversation=self.conversation.add_message(message),
            context_window=self.context_window.with_added_tokens(tokens),
            status=SessionStatus.ACTIVE,
        )

    def record_usage(self, usage: TokenUsage) -> Session:
        """Add provider-reported usage to the aggregate."""
        return replace(self, token_usage=self.token_usage.add(usage))

    def needs_compaction(self, threshold_ratio: float | None = None) -> bool:
        """Return whether the context window requests compaction."""
        return self.context_window.needs_compaction(threshold_ratio)

    def compact_context(
        self,
        compactor: ContextCompactor | None = None,
        summary: str | None = None,
    ) -> tuple[Session, CompactionResult]:
        """Compact the conversation and return the updated session and result."""
        active_compactor = compactor or ContextCompactor()
        conversation, window, result = active_compactor.compact(
            self.conversation, self.context_window, summary=summary
        )
        return (
            replace(
                self,
                conversation=conversation,
                context_window=window,
                compaction_count=self.compaction_count + 1,
            ),
            result,
        )

    def complete(self) -> Session:
        """Mark the session completed."""
        return replace(self, status=SessionStatus.COMPLETED)

    def fail(self) -> Session:
        """Mark the session failed."""
        return replace(self, status=SessionStatus.FAILED)

    def with_status(self, status: SessionStatus) -> Session:
        """Return the session with a replacement status."""
        return replace(self, status=status)

    def with_metadata(self, key: str, value: Any) -> Session:
        """Return the session with one metadata field replaced."""
        return replace(self, metadata={**self.metadata, key: value})
