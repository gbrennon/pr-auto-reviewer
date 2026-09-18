"""Result of compacting a conversation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .token_count import TokenCount


@dataclass(frozen=True)
class CompactionResult:
    """Immutable measurements and summary produced by compaction."""

    original_tokens: TokenCount
    compacted_tokens: TokenCount
    messages_before: int
    messages_after: int
    summary: str
    tokens_freed: TokenCount = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tokens_freed",
            self.original_tokens.saturating_sub(self.compacted_tokens),
        )

    @property
    def compression_ratio(self) -> float:
        """Return compacted tokens as a fraction of original tokens."""
        return self.compacted_tokens.ratio(self.original_tokens)

    @property
    def messages_removed(self) -> int:
        """Return the number of removed messages."""
        return self.messages_before - self.messages_after

    @property
    def did_compact(self) -> bool:
        """Whether compaction freed at least one token."""
        return self.tokens_freed > TokenCount.ZERO
