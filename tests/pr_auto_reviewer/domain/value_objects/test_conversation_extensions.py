"""Tests for Conversation token-aware sequence APIs."""

from pr_auto_reviewer.domain.value_objects.conversation import Conversation
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.token_count import TokenCount


class TestConversationExtensions:
    """Sequence access and token estimation behavior."""

    def test_supports_length_iteration_and_indexing(self) -> None:
        messages = (
            ConversationMessage(role="system", content="rules"),
            ConversationMessage(role="user", content="hello"),
        )
        conversation = Conversation(messages=messages)

        assert len(conversation) == 2
        assert tuple(conversation) == messages
        assert conversation[0] == messages[0]
        assert conversation[0:1] == messages[:1]

    def test_finds_system_message_and_replaces_messages(self) -> None:
        conversation = Conversation(messages=(
            ConversationMessage(role="user", content="hello"),
            ConversationMessage(role="system", content="rules"),
        ))

        replacement = conversation.replace_messages(conversation.messages[:1])

        assert conversation.system_message() == conversation.messages[1]
        assert replacement.messages == conversation.messages[:1]

    def test_estimates_tokens(self) -> None:
        conversation = Conversation(messages=(
            ConversationMessage(role="user", content="abcd"),
        ))

        assert conversation.estimate_tokens() == TokenCount(4)
