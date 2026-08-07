"""ConversationMessage — a single message in an agentic conversation."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.agent.tool_call import ToolCall
from pr_auto_reviewer.domain.agent.tool_result import ToolResult


@dataclass(frozen=True)
class ConversationMessage:
    """One message in a multi-turn agentic conversation.

    The ``role`` is one of ``"system"``, ``"user"``, ``"assistant"``,
    or ``"tool"``. Tool-call and tool-result payloads are carried in
    the optional ``tool_call`` and ``tool_result`` fields.
    """

    role: str
    content: str
    tool_call: ToolCall | None = None
    tool_result: ToolResult | None = None
