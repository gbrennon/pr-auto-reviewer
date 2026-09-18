"""Tests for TokenCount."""

import pytest

from pr_auto_reviewer.domain.exceptions import InvalidTokenCountError
from pr_auto_reviewer.domain.value_objects.conversation import Conversation
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.token_count import TokenCount
from pr_auto_reviewer.domain.value_objects.tool_call import ToolCall
from pr_auto_reviewer.domain.value_objects.tool_result import ToolResult


class TestTokenCount:
    """Token count arithmetic and estimation behavior."""

    def test_rejects_negative_values(self) -> None:
        with pytest.raises(InvalidTokenCountError, match="non-negative"):
            TokenCount(-1)

    def test_arithmetic_accepts_counts_and_integers(self) -> None:
        count = TokenCount(5)

        assert count + TokenCount(2) == TokenCount(7)
        assert count + 2 == TokenCount(7)
        assert count - 2 == TokenCount(3)

    def test_subtraction_rejects_negative_result(self) -> None:
        with pytest.raises(InvalidTokenCountError, match="negative"):
            TokenCount(2) - 3

    def test_saturating_subtraction_floors_at_zero(self) -> None:
        assert TokenCount(2).saturating_sub(3) is TokenCount.ZERO

    def test_comparison_ratio_and_zero_properties(self) -> None:
        count = TokenCount(4)

        assert count > TokenCount.ZERO
        assert count >= 4
        assert count < 5
        assert count <= 4
        assert count.ratio(8) == 0.5
        assert count.ratio(0) == 0.0
        assert TokenCount.ZERO.is_zero
        assert int(count) == 4
        assert str(count) == "4"

    def test_from_text_uses_character_heuristic(self) -> None:
        assert TokenCount.from_text("12345") == TokenCount(2)
        assert TokenCount.from_text("") is TokenCount.ZERO

    def test_from_message_includes_payload_overhead(self) -> None:
        message = ConversationMessage(
            role="assistant",
            content="abcd",
            tool_call=ToolCall(tool_name="read", arguments={"path": "x"}),
            tool_result=ToolResult(status="success", data={"value": "ok"}),
        )

        assert message.estimate_tokens(chars_per_token=4.0) == TokenCount(12)

    def test_from_conversation_sums_messages(self) -> None:
        conversation = Conversation(messages=(
            ConversationMessage(role="user", content="abcd"),
            ConversationMessage(role="assistant", content="12345678"),
        ))

        assert TokenCount.from_conversation(conversation) == TokenCount(9)
