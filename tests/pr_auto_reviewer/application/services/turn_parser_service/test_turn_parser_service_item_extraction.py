import json

from ._helpers import *


class TestTurnParserServiceItemExtraction:
    """TurnParserService must pass normalized item dicts into raw_items."""

    def test_verdict_branch_normalizes_supplied_aliases(self) -> None:
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=json.dumps({
            "verdict": "Needs Improvement",
            "reason": "lacks error handling",
            "summary": "The error path needs a fix.",
            "items": [
                {"file": "src/a.py", "description": "No error handling.",
                 "category": "correctness", "severity": "High"},
            ],
            "suggestions": [],
            "praise": [],
        })))
        assert result.kind is TurnKind.VERDICT
        assert result.raw_items is not None
        assert len(result.raw_items) == 1
        assert result.raw_items[0]["description"] == "No error handling."
        assert result.raw_items[0]["severity"] == "major"
        assert result.raw_items[0]["category"] == "bug"

    def test_missing_item_field_is_unparseable(self) -> None:
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=json.dumps({
            "verdict": "approved",
            "reason": "r",
            "summary": "s",
            "items": [{"file": "x.py", "severity": "major"}],
            "suggestions": [],
            "praise": [],
        })))

        assert result.kind is TurnKind.UNPARSEABLE

    def test_prose_findings_without_explicit_envelope_are_unparseable(self) -> None:
        content = (
            "#### 1. Hardcoded timeout in `src/a.py` [major]\n"
            "The module hardcodes a timeout instead of reading config.\n"
            "```python\n"
            "TIMEOUT = 30\n"
            "```\n"
            "Suggested fix:\n"
            "```python\n"
            "TIMEOUT = settings.timeout\n"
            "```\n"
        )
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=content))

        assert result.kind is TurnKind.UNPARSEABLE
