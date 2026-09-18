"""ConversationMessage — a single message in an agentic conversation."""

from __future__ import annotations

from dataclasses import dataclass

from .token_count import TokenCount
from .tool_call import ToolCall
from .tool_result import ToolResult


@dataclass(frozen=True)
class ConversationMessage:
    """One message in a multi-turn agentic conversation.

    The ``role`` is one of ``"system"``, ``"user"``, ``"assistant"``,
    or ``"tool"``. Tool-call and tool-result payloads are carried in the
    optional ``tool_call`` and ``tool_result`` fields.
    """

    role: str
    content: str
    tool_call: ToolCall | None = None
    tool_result: ToolResult | None = None

    def estimate_tokens(self, chars_per_token: float = 4.0) -> TokenCount:
        """Estimate the tokens represented by this message."""
        return TokenCount.from_message(self, chars_per_token)
