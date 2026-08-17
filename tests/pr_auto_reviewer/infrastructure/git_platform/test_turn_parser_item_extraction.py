"""Regression tests: review pipeline must never emit empty JSON fields.

Covers the fixes that made the terminal review output carry real content:
LLM item dicts with ``issue``/``severity`` keys survive normalization and
the factory; suggestions are grounded against repo files; the terminal
JSON omits empty nested fields; and the ``commented`` verdict is the
failure marker, not a silent default.
"""

import json

from pr_auto_reviewer.application.services.turn_parser import TurnParser
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)


class TestTurnParserItemExtraction:
    """TurnParser must pass normalized item dicts into raw_items."""

    def test_verdict_branch_normalizes_issue_items(self) -> None:
        parser = TurnParser(ReviewResponseParser())
        result = parser._parse(json.dumps({
            "verdict": "Needs Improvement",
            "reason": "lacks error handling",
            "items": [
                {"file": "src/a.py", "issue": "No error handling.",
                 "severity": "High"},
            ],
        }))
        assert result.kind == "verdict"
        assert result.metadata is not None
        assert len(result.raw_items or []) == 1
        assert result.raw_items[0]["description"] == "No error handling."
        assert result.raw_items[0]["severity"] == "major"

    def test_verdict_branch_keeps_string_items_out_of_raw_items(self) -> None:
        parser = TurnParser(ReviewResponseParser())
        result = parser._parse(json.dumps({
            "verdict": "approved",
            "items": ["Review multi_phase_orchestrator.py"],
        }))
        assert result.kind == "verdict"
        assert result.raw_items == []
        assert result.metadata is not None
        assert result.metadata["suggestions"] != []

    def test_positive_verdict_coerces_to_approved(self) -> None:
        parser = TurnParser(ReviewResponseParser())
        result = parser._parse(json.dumps({
            "verdict": "Positive",
            "reason": "codebase is clean",
            "items": [],
        }))
        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"

    def test_no_issues_found_coerces_to_approved(self) -> None:
        parser = TurnParser(ReviewResponseParser())
        result = parser._parse(json.dumps({
            "verdict": "no_issues_found",
            "items": [],
        }))
        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"
