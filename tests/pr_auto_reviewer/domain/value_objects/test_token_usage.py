"""Tests for TokenUsage."""

from pr_auto_reviewer.domain.value_objects.token_count import TokenCount
from pr_auto_reviewer.domain.value_objects.token_usage import TokenUsage


class TestTokenUsage:
    """Prompt and completion token aggregation."""

    def test_defaults_are_zero(self) -> None:
        usage = TokenUsage()

        assert usage.prompt_tokens is TokenCount.ZERO
        assert usage.completion_tokens is TokenCount.ZERO
        assert usage.total_tokens is TokenCount.ZERO

    def test_add_combines_prompt_and_completion_tokens(self) -> None:
        first = TokenUsage(TokenCount(3), TokenCount(4))
        second = TokenUsage(TokenCount(2), TokenCount(5))

        assert first.add(second) == TokenUsage(TokenCount(5), TokenCount(9))

    def test_with_methods_return_replaced_immutable_values(self) -> None:
        usage = TokenUsage(TokenCount(3), TokenCount(4))

        assert usage.with_prompt_tokens(8) == TokenUsage(TokenCount(8), TokenCount(4))
        assert usage.with_completion_tokens(TokenCount(9)) == TokenUsage(
            TokenCount(3), TokenCount(9)
        )
        assert usage == TokenUsage(TokenCount(3), TokenCount(4))
