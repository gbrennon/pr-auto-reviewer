"""TokenBudgetManager — tracks token consumption within a budget limit."""

from __future__ import annotations


class TokenBudgetManager:
    """Manages token budget for prompt composition.

    Prevents exceeding the LLM context window by tracking cumulative
    token consumption across multiple texts.

    Token estimation uses a rough heuristic: **1 token ≈ 4 characters**.
    For production use, this can be upgraded to the ``tiktoken`` library
    for exact counting.
    """

    def __init__(self, max_tokens: int) -> None:
        """Initialise with a maximum token budget.

        Args:
            max_tokens: Hard limit on total tokens consumed.
        """
        self._max_tokens = max_tokens
        self._consumed = 0

    # ------------------------------------------------------------------
    # Token estimation
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Return an estimated token count for *text*.

        Uses the rough heuristic ``len(text) // 4``.
        """
        return len(text) // 4

    # ------------------------------------------------------------------
    # Budget queries
    # ------------------------------------------------------------------

    def fits_budget(self, text: str) -> bool:
        """Return ``True`` if *text* fits within the remaining budget."""
        tokens = self.estimate_tokens(text)
        return self._consumed + tokens <= self._max_tokens

    def remaining(self) -> int:
        """Return the number of tokens still available."""
        return self._max_tokens - self._consumed

    # ------------------------------------------------------------------
    # Budget consumption
    # ------------------------------------------------------------------

    def consume(self, text: str) -> int:
        """Consume budget for *text* and return tokens consumed.

        Raises:
            ValueError: If *text* would exceed the remaining budget.
        """
        tokens = self.estimate_tokens(text)

        if self._consumed + tokens > self._max_tokens:
            raise ValueError(
                f"Text would exceed budget: {tokens} tokens needed, "
                f"{self.remaining()} remaining",
            )

        self._consumed += tokens
        return tokens

    def reset(self) -> None:
        """Reset consumed tokens to zero (start a new budget cycle)."""
        self._consumed = 0
