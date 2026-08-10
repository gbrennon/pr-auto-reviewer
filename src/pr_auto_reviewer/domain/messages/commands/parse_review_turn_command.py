"""ParseReviewTurnCommand — input for parsing a single LLM conversation turn."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParseReviewTurnCommand:
    """Command to parse a raw LLM response into a structured TurnParseResult."""

    content: str
