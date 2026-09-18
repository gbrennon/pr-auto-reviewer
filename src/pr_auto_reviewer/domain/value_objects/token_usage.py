"""Immutable prompt and completion token usage."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .token_count import TokenCount


@dataclass(frozen=True)
class TokenUsage:
    """Token usage reported for a model exchange."""

    prompt_tokens: TokenCount = field(default_factory=lambda: TokenCount.ZERO)
    completion_tokens: TokenCount = field(default_factory=lambda: TokenCount.ZERO)

    @property
    def total_tokens(self) -> TokenCount:
        """Return prompt and completion tokens combined."""
        return self.prompt_tokens + self.completion_tokens

    def add(self, other: TokenUsage) -> TokenUsage:
        """Return usage with another exchange added."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )

    def with_prompt_tokens(self, tokens: TokenCount | int) -> TokenUsage:
        """Return usage with a new prompt count."""
        return replace(self, prompt_tokens=TokenCount(self._as_int(tokens)))

    def with_completion_tokens(self, tokens: TokenCount | int) -> TokenUsage:
        """Return usage with a new completion count."""
        return replace(self, completion_tokens=TokenCount(self._as_int(tokens)))

    @staticmethod
    def _as_int(tokens: TokenCount | int) -> int:
        return int(tokens) if isinstance(tokens, TokenCount) else tokens
