"""Immutable token-count arithmetic and conversation estimation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ..exceptions.invalid_token_count_error import InvalidTokenCountError

if TYPE_CHECKING:
    from .conversation import Conversation
    from .conversation_message import ConversationMessage


@dataclass(frozen=True, eq=False)
class TokenCount:
    """A non-negative number of model tokens."""

    value: int = 0
    ZERO: ClassVar[TokenCount]

    def __post_init__(self) -> None:
        if self.value < 0:
            raise InvalidTokenCountError("token count must be non-negative")

    @staticmethod
    def _coerce(other: TokenCount | int) -> int:
        if isinstance(other, TokenCount):
            return other.value
        if isinstance(other, int):
            return other
        raise TypeError(f"expected TokenCount or int, got {type(other).__name__}")

    def __add__(self, other: TokenCount | int) -> TokenCount:
        result = self.value + self._coerce(other)
        return TokenCount.ZERO if result == 0 else TokenCount(result)

    def __sub__(self, other: TokenCount | int) -> TokenCount:
        result = self.value - self._coerce(other)
        if result < 0:
            raise InvalidTokenCountError("token subtraction cannot be negative")
        return TokenCount(result)

    def saturating_sub(self, other: TokenCount | int) -> TokenCount:
        result = self.value - self._coerce(other)
        return TokenCount.ZERO if result <= 0 else TokenCount(result)

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)

    def __lt__(self, other: TokenCount | int) -> bool:
        return self.value < self._coerce(other)

    def __le__(self, other: TokenCount | int) -> bool:
        return self.value <= self._coerce(other)

    def __gt__(self, other: TokenCount | int) -> bool:
        return self.value > self._coerce(other)

    def __ge__(self, other: TokenCount | int) -> bool:
        return self.value >= self._coerce(other)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TokenCount):
            return self.value == other.value
        if isinstance(other, int):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)

    @property
    def is_zero(self) -> bool:
        """Whether this count is zero."""
        return self.value == 0

    def ratio(self, total: TokenCount | int) -> float:
        """Return this count as a fraction of *total*."""
        total_value = self._coerce(total)
        return self.value / total_value if total_value > 0 else 0.0

    @classmethod
    def from_text(cls, text: str, chars_per_token: float = 4.0) -> TokenCount:
        """Estimate tokens from text length using a character heuristic."""
        if chars_per_token <= 0.0:
            raise ValueError("chars_per_token must be positive")
        if not text:
            return cls.ZERO
        return cls(math.ceil(len(text) / chars_per_token))

    @classmethod
    def from_message(
        cls, message: ConversationMessage, chars_per_token: float = 4.0
    ) -> TokenCount:
        """Estimate tokens for message text and attached tool payloads."""
        total = cls.from_text(message.content, chars_per_token) + 3
        if message.tool_call is not None:
            tool_payload = message.tool_call.tool_name + json.dumps(
                message.tool_call.arguments, sort_keys=True, separators=(",", ":")
            )
            total += cls.from_text(tool_payload, chars_per_token)
        if message.tool_result is not None:
            result_content = (
                json.dumps(
                    message.tool_result.data,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                if message.tool_result.data is not None
                else message.tool_result.error or ""
            )
            total += cls.from_text(result_content, chars_per_token)
        return total

    @classmethod
    def from_conversation(
        cls, conversation: Conversation, chars_per_token: float = 4.0
    ) -> TokenCount:
        """Estimate tokens for every message in a conversation."""
        return sum(
            (cls.from_message(message, chars_per_token) for message in conversation),
            cls.ZERO,
        )


TokenCount.ZERO = TokenCount(0)
