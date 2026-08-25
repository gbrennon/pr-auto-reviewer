"""ParseReviewTurnPort — inbound port for parsing a single LLM conversation turn."""

from typing import Protocol

from pr_auto_reviewer.domain.messages.commands.parse_review_turn_command import (
    ParseReviewTurnCommand,
)
from pr_auto_reviewer.domain.value_objects.turn_parse_result import TurnParseResult


class ParseReviewTurnPort(Protocol):
    """Parse a raw LLM response into a structured TurnParseResult."""

    def execute(self, command: ParseReviewTurnCommand) -> TurnParseResult:
        ...
