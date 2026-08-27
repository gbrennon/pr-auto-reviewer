"""Shared helpers, fixtures, and imports for the split test modules."""

import json
from typing import Any

from pr_auto_reviewer.application.services.turn_parser_service import TurnParserService
from pr_auto_reviewer.domain.messages.commands.parse_review_turn_command import (
    ParseReviewTurnCommand,
)
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.value_objects.turn_kind import TurnKind
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)


def make_parser(
    *,
    items: list[dict] | None = None,
    observations: list[dict] | None = None,
    extracted_json: str | None = None,
    verdict: ReviewVerdict = ReviewVerdict.APPROVED,
    prose_suggestions: list[dict] | None = None,
    prose_praise: list[dict] | None = None,
) -> FakeResponseParser:
    """Create a configured fake parser for testing."""
    return FakeResponseParser(
        items=items,
        observations=observations,
        extracted_json=extracted_json,
        verdict=verdict,
        prose_suggestions=prose_suggestions,
        prose_praise=prose_praise,
    )


__all__ = ['Any', 'FakeResponseParser', 'ParseReviewTurnCommand', 'ReviewResponseParser', 'ReviewVerdict', 'TurnKind', 'TurnParserService', 'json', 'make_parser']


class FakeResponseParser:
    """Fake parser implementation for testing TurnParserService."""

    def __init__(
        self,
        *,
        items: list[dict] | None = None,
        observations: list[dict] | None = None,
        extracted_json: str | None = None,
        verdict: ReviewVerdict = ReviewVerdict.APPROVED,
        prose_suggestions: list[dict] | None = None,
        prose_praise: list[dict] | None = None,
    ) -> None:
        self._items = items if items is not None else []
        self._observations = observations if observations is not None else []
        self._extracted_json = extracted_json
        self._verdict = verdict
        self._prose_suggestions = prose_suggestions if prose_suggestions is not None else []
        self._prose_praise = prose_praise if prose_praise is not None else []

    def parse_items(self, raw_text: str) -> list[dict[str, Any]]:
        return self._items

    def parse_item_observations(self, raw_text: str) -> list[dict[str, Any]]:
        return self._observations

    def sanitize_json_literals(self, text: str) -> str:
        return text

    def extract_outermost_json(self, text: str) -> str | None:
        return self._extracted_json

    def extract_verdict_md(self, raw_text: str) -> ReviewVerdict:
        return self._verdict

    def parse_prose_recommendations(self, raw_text: str) -> list[dict[str, Any]]:
        return self._prose_suggestions

    def parse_prose_praise(self, raw_text: str) -> list[dict[str, Any]]:
        return self._prose_praise

    def normalize_item_dict(self, item: dict[str, Any]) -> dict[str, Any]:
        return item

    def strip_frontmatter(self, text: str) -> str:
        return text
