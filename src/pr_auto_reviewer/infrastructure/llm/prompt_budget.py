from __future__ import annotations

from dataclasses import dataclass, field

@dataclass
class PromptBudget:
    max_tokens: int
    _consumed: int = field(default=0, init=False, repr=False)

    @property
    def consumed_tokens(self) -> int:
        return self._consumed

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self._consumed)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // 4

    def consume(self, text: str) -> int:
        tokens = self.estimate_tokens(text)
        self._consumed += tokens
        return tokens

    def would_fit(self, text: str) -> bool:
        return self._consumed + self.estimate_tokens(text) <= self.max_tokens

    def try_consume(self, text: str) -> bool:
        if self.would_fit(text):
            self.consume(text)
            return True
        return False
