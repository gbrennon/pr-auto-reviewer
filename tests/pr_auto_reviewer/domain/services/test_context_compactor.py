"""Tests for ContextCompactor."""

from pr_auto_reviewer.domain.services.context_compactor import ContextCompactor
from pr_auto_reviewer.domain.value_objects.compaction_policy import CompactionPolicy
from pr_auto_reviewer.domain.value_objects.context_window import ContextWindow
from pr_auto_reviewer.domain.value_objects.conversation import Conversation
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.token_count import TokenCount
from pr_auto_reviewer.domain.value_objects.tool_call import ToolCall


class TestContextCompactor:
    """Conversation pruning and summary behavior."""

    def test_preserves_system_prompt_and_recent_messages(self) -> None:
        messages = (
            ConversationMessage(role="system", content="rules"),
            ConversationMessage(role="user", content="old user " + "x" * 80),
            ConversationMessage(role="assistant", content="old answer " + "x" * 80),
            ConversationMessage(role="user", content="recent user"),
            ConversationMessage(role="assistant", content="recent answer"),
        )
        conversation = Conversation(messages=messages)
        policy = CompactionPolicy(preserve_recent_messages=2)
        compacted, _, result = ContextCompactor(policy).compact(
            conversation, ContextWindow(max_tokens=TokenCount(500)), summary="kept facts"
        )

        assert compacted.messages[0] == messages[0]
        assert compacted.messages[1].content.endswith("kept facts")
        assert compacted.messages[-2:] == messages[-2:]
        assert result.messages_removed == 1
        assert result.did_compact

    def test_generated_summary_mentions_turns_and_tools(self) -> None:
        conversation = Conversation(messages=(
            ConversationMessage(role="system", content="rules"),
            ConversationMessage(role="user", content="question"),
            ConversationMessage(
                role="assistant",
                content="calling tool",
                tool_call=ToolCall(tool_name="read_file", arguments={}),
            ),
            ConversationMessage(role="tool", content="result"),
            ConversationMessage(role="assistant", content="recent"),
        ))

        compacted, _, _ = ContextCompactor(
            CompactionPolicy(preserve_recent_messages=1)
        ).compact(conversation, ContextWindow(max_tokens=TokenCount(500)))

        assert "user=1" in compacted.messages[1].content
        assert "assistant=1" in compacted.messages[1].content
        assert "tool=1" in compacted.messages[1].content
        assert "read_file" in compacted.messages[1].content

    def test_short_conversation_is_unchanged(self) -> None:
        conversation = Conversation(messages=(
            ConversationMessage(role="user", content="hello"),
            ConversationMessage(role="assistant", content="hi"),
        ))
        window = ContextWindow(max_tokens=TokenCount(500), current_tokens=TokenCount(8))

        compacted, returned_window, result = ContextCompactor().compact(conversation, window)

        assert compacted == conversation
        assert returned_window == window
        assert not result.did_compact
        assert result.summary == "(no compaction needed)"
