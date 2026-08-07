"""ReviewTurnParsedEvent — emitted when a single conversation turn is parsed."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.agent.turn_parse_result import TurnParseResult


@dataclass(frozen=True)
class ReviewTurnParsedEvent:
    """Emitted when a single LLM response is parsed into a TurnParseResult."""

    turn_number: int
    result: TurnParseResult
