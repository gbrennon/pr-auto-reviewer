"""Tests for the Conversation domain object."""

from pr_auto_reviewer.domain.agent.conversation import Conversation
from pr_auto_reviewer.domain.agent.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.agent.tool_call import ToolCall


class TestConversation:
    """Behaviour of the immutable Conversation message sequence."""

    def test_new_conversation_starts_empty(self) -> None:
        conversation = Conversation()
        assert conversation.messages == ()

    def test_add_message_appends_to_new_instance(self) -> None:
        message = ConversationMessage(role="user", content="hello")
        conversation = Conversation().add_message(message)
        assert conversation.messages == (message,)

    def test_add_message_preserves_existing_messages(self) -> None:
        first = ConversationMessage(role="user", content="first")
        second = ConversationMessage(role="assistant", content="second")
        conversation = Conversation(messages=(first,)).add_message(second)
        assert conversation.messages == (first, second)

    def test_add_message_does_not_mutate_original(self) -> None:
        first = ConversationMessage(role="user", content="first")
        original = Conversation(messages=(first,))
        original.add_message(ConversationMessage(role="user", content="second"))
        assert original.messages == (first,)

    def test_last_assistant_message_returns_most_recent(self) -> None:
        user = ConversationMessage(role="user", content="prompt")
        first = ConversationMessage(role="assistant", content="first")
        second = ConversationMessage(role="assistant", content="second")
        conversation = Conversation(messages=(user, first, second))
        assert conversation.last_assistant_message() == second

    def test_last_assistant_message_returns_none_when_none(self) -> None:
        conversation = Conversation(messages=(
            ConversationMessage(role="user", content="prompt"),
        ))
        assert conversation.last_assistant_message() is None

    def test_tool_call_count_counts_tool_call_messages(self) -> None:
        tool_call = ToolCall(tool_name="read_file", arguments={"file": "a.py"})
        conversation = Conversation(messages=(
            ConversationMessage(role="user", content="prompt"),
            ConversationMessage(
                role="assistant", content='{"action": "read_file"}',
                tool_call=tool_call,
            ),
            ConversationMessage(role="user", content="result"),
        ))
        assert conversation.tool_call_count() == 1

    def test_tool_call_count_zero_when_none(self) -> None:
        conversation = Conversation(messages=(
            ConversationMessage(role="user", content="prompt"),
            ConversationMessage(role="assistant", content="reply"),
        ))
        assert conversation.tool_call_count() == 0
