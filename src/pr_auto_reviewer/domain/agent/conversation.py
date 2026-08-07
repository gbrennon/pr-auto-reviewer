"""Conversation — an ordered sequence of messages in an agentic review."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.agent.conversation_message import (
    ConversationMessage,
)


@dataclass(frozen=True)
class Conversation:
    """An immutable sequence of messages in an agentic review conversation.

    Mutation methods return new instances; the original is never modified.
    """

    messages: tuple[ConversationMessage, ...] = ()

    def add_message(self, message: ConversationMessage) -> Conversation:
        """Return a new Conversation with *message* appended."""
        return Conversation(messages=(*self.messages, message))

    def last_assistant_message(self) -> ConversationMessage | None:
        """Return the most recent assistant message, or None."""
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                return msg
        return None

    def tool_call_count(self) -> int:
        """Return the number of tool-call messages in the conversation."""
        return sum(1 for msg in self.messages if msg.tool_call is not None)
