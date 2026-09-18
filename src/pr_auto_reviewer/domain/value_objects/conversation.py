"""Conversation — an ordered sequence of messages in an agentic review."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from .conversation_message import ConversationMessage
from .token_count import TokenCount


@dataclass(frozen=True)
class Conversation:
    """An immutable sequence of messages in an agentic review.

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

    def __len__(self) -> int:
        """Return the number of messages."""
        return len(self.messages)

    def __iter__(self) -> Iterator[ConversationMessage]:
        """Iterate over messages in order."""
        return iter(self.messages)

    def __getitem__(
        self, index: int | slice
    ) -> ConversationMessage | tuple[ConversationMessage, ...]:
        """Return one message or a tuple slice."""
        return self.messages[index]

    def system_message(self) -> ConversationMessage | None:
        """Return the first system message, or None."""
        return next((message for message in self.messages if message.role == "system"), None)

    def estimate_tokens(self, chars_per_token: float = 4.0) -> TokenCount:
        """Estimate tokens for all messages."""
        return TokenCount.from_conversation(self, chars_per_token)

    def replace_messages(self, messages: Sequence[ConversationMessage]) -> Conversation:
        """Return a conversation containing a replacement message sequence."""
        return Conversation(messages=tuple(messages))
