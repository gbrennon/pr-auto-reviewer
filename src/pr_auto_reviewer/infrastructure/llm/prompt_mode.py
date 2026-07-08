from __future__ import annotations

from enum import StrEnum

class PromptMode(StrEnum):
    """Enumeration of prompt composition modes for LLM usage.

    This lives in the infrastructure.llm package because prompt composition is an
    LLM/infrastructure concern, not application domain logic.
    """

    MONOLITHIC = "monolithic"
    FRAGMENTS = "fragments"

    @classmethod
    def parse(cls, raw: str) -> "PromptMode":
        if not raw:
            return cls.MONOLITHIC
        r = raw.strip().lower()
        if r in ("fragments", "fragment", "frags"):
            return cls.FRAGMENTS
        return cls.MONOLITHIC
