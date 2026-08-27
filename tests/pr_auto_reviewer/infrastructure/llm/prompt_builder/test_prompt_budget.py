from ._helpers import *


class TestPromptBudget:
    def test_estimate_tokens_rough_heuristic(self):
        """1 token ≈ 4 characters."""
        text = "a" * 100
        assert PromptBudget.estimate_tokens(text) == 25

    def test_consume_increases_consumed(self):
        budget = PromptBudget(max_tokens=100)
        budget.consume("a" * 40)
        assert budget._consumed == 10
        assert budget.remaining_tokens == 90

    def test_would_fit_returns_true_when_room(self):
        budget = PromptBudget(max_tokens=100)
        assert budget.would_fit("a" * 200) is True
        assert budget.would_fit("a" * 500) is False

    def test_try_consume_consumes_if_fits(self):
        budget = PromptBudget(max_tokens=50)
        assert budget.try_consume("a" * 100) is True
        assert budget.try_consume("a" * 200) is False
        assert budget._consumed == 25

    def test_remaining_tokens_never_negative(self):
        budget = PromptBudget(max_tokens=10)
        budget.consume("a" * 100)
        assert budget.remaining_tokens == 0

