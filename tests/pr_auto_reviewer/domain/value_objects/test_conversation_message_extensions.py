"""Tests for ConversationMessage token estimation."""

from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.token_count import TokenCount


class TestConversationMessageExtensions:
    """Token estimation behavior."""

    def test_estimate_tokens_delegates_to_message_heuristic(self) -> None:
        message = ConversationMessage(role="user", content="12345678")

        assert message.estimate_tokens() == TokenCount(5)
