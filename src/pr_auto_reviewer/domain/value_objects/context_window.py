"""Context-window capacity and utilization value object."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ..exceptions.context_window_exceeded_error import ContextWindowExceededError
from ..exceptions.invalid_token_count_error import InvalidTokenCountError
from .token_count import TokenCount


@dataclass(frozen=True)
class ContextWindow:
    """Immutable model context capacity and current consumption."""

    max_tokens: TokenCount
    current_tokens: TokenCount = field(default_factory=lambda: TokenCount.ZERO)
    reserved_output_tokens: TokenCount = field(default_factory=lambda: TokenCount.ZERO)
    compact_threshold_ratio: float = 0.8

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_tokens", self._as_count(self.max_tokens))
        object.__setattr__(self, "current_tokens", self._as_count(self.current_tokens))
        object.__setattr__(
            self,
            "reserved_output_tokens",
            self._as_count(self.reserved_output_tokens),
        )
        if int(self.max_tokens) <= 0:
            raise InvalidTokenCountError("max_tokens must be positive")
        if not 0.0 < self.compact_threshold_ratio <= 1.0:
            raise ValueError("compact_threshold_ratio must be in (0.0, 1.0]")
        if int(self.reserved_output_tokens) >= int(self.max_tokens):
            raise ContextWindowExceededError(
                "reserved_output_tokens must be strictly less than max_tokens"
            )

    @staticmethod
    def _as_count(tokens: TokenCount | int) -> TokenCount:
        return tokens if isinstance(tokens, TokenCount) else TokenCount(tokens)

    @property
    def effective_capacity(self) -> TokenCount:
        """Return capacity after reserving output tokens."""
        return self.max_tokens - self.reserved_output_tokens

    @property
    def available_tokens(self) -> TokenCount:
        """Return remaining input capacity, floored at zero."""
        return self.effective_capacity.saturating_sub(self.current_tokens)

    @property
    def utilization(self) -> float:
        """Return current input utilization as a ratio."""
        return self.current_tokens.ratio(self.effective_capacity)

    @property
    def is_exhausted(self) -> bool:
        """Whether current tokens meet or exceed effective capacity."""
        return int(self.current_tokens) >= int(self.effective_capacity)

    def needs_compaction(self, threshold_ratio: float | None = None) -> bool:
        """Whether utilization has reached the configured threshold."""
        threshold = (
            self.compact_threshold_ratio
            if threshold_ratio is None
            else threshold_ratio
        )
        return self.utilization >= threshold or self.is_exhausted

    def can_fit(self, tokens: TokenCount | int) -> bool:
        """Whether additional tokens fit within effective capacity."""
        return int(self.current_tokens) + int(self._as_count(tokens)) <= int(
            self.effective_capacity
        )

    def with_current_tokens(self, tokens: TokenCount | int) -> ContextWindow:
        """Return a window with a replacement current token count."""
        return replace(self, current_tokens=self._as_count(tokens))

    def with_added_tokens(self, added: TokenCount | int) -> ContextWindow:
        """Return a window with additional current tokens."""
        return replace(self, current_tokens=self.current_tokens + added)

    def with_reserved_output(self, reserved: TokenCount | int) -> ContextWindow:
        """Return a window with a replacement output reservation."""
        return replace(self, reserved_output_tokens=self._as_count(reserved))
