from ._shared import *


@dataclass
class PromptBudget:
    """Tracks token consumption for budget-aware prompt construction.

    Uses a rough heuristic of 1 token ≈ 4 characters. For production use
    with more accurate counting, integrate ``tiktoken``.
    """

    max_tokens: int
    _consumed: int = field(default=0, init=False, repr=False)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self._consumed)

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """Rough token estimate: 1 token ≈ 4 characters."""
        return len(text) // 4

    def consume(self, text: str) -> int:
        """Mark *text* as consumed, return its estimated token count."""
        tokens = self.estimate_tokens(text)
        self._consumed += tokens
        return tokens

    def would_fit(self, text: str) -> bool:
        """Return True if *text* fits within the remaining budget."""
        return self._consumed + self.estimate_tokens(text) <= self.max_tokens

    def try_consume(self, text: str) -> bool:
        """Consume *text* if it fits; return True when consumed."""
        if self.would_fit(text):
            self.consume(text)
            return True
        return False

