"""Unit tests for TokenBudgetManager — pure logic, no I/O."""

import pytest

from pr_auto_reviewer.application.services.token_budget_manager import (
    TokenBudgetManager,
)


class TestTokenBudgetManager:
    """Tests for TokenBudgetManager token counting and budget control."""

    def test_estimates_tokens_from_text(self) -> None:
        """Should estimate token count from text (4 chars ≈ 1 token)."""
        manager = TokenBudgetManager(max_tokens=1000)
        text = "a" * 400

        tokens = manager.estimate_tokens(text)

        assert tokens == 100

    def test_checks_if_content_fits_budget(self) -> None:
        """Should check if content fits within remaining budget."""
        manager = TokenBudgetManager(max_tokens=100)

        small_text = "a" * 200  # ~50 tokens
        large_text = "a" * 600  # ~150 tokens

        assert manager.fits_budget(small_text) is True
        assert manager.fits_budget(large_text) is False

    def test_calculates_remaining_budget_after_consumption(self) -> None:
        """Should track remaining budget after consuming tokens."""
        manager = TokenBudgetManager(max_tokens=1000)
        text = "a" * 400  # ~100 tokens

        manager.consume(text)

        assert manager.remaining() == 900

    def test_raises_when_consumption_exceeds_budget(self) -> None:
        """Should raise ValueError when text would exceed budget."""
        manager = TokenBudgetManager(max_tokens=100)

        with pytest.raises(
            ValueError, match="Text would exceed budget",
        ):
            manager.consume("a" * 600)  # ~150 tokens > 100 budget

    def test_reset_clears_consumed_tokens(self) -> None:
        """Reset should clear consumed tokens back to zero."""
        manager = TokenBudgetManager(max_tokens=1000)
        manager.consume("a" * 400)  # ~100 tokens

        manager.reset()

        assert manager.remaining() == 1000

    def test_cumulative_consumption(self) -> None:
        """Should track cumulative consumption across multiple texts."""
        manager = TokenBudgetManager(max_tokens=500)

        manager.consume("a" * 200)  # 50 tokens
        manager.consume("b" * 400)  # 100 tokens

        assert manager.remaining() == 350

    def test_initial_remaining_equals_max(self) -> None:
        """Remaining should equal max_tokens before any consumption."""
        manager = TokenBudgetManager(max_tokens=4096)

        assert manager.remaining() == 4096
