"""Regression tests: review pipeline must never emit empty JSON fields.

Covers the fixes that made the terminal review output carry real content:
LLM item dicts with ``issue``/``severity`` keys survive normalization and
the factory; suggestions are grounded against repo files; the terminal
JSON omits empty nested fields; and the ``commented`` verdict is the
failure marker, not a silent default.
"""

from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)


class TestItemDictNormalization:
    """LLM items using ``issue``/``severity`` keys must survive parsing."""

    def test_issue_key_maps_to_description_and_suggested_fix(self) -> None:
        normalized = ReviewResponseParser._normalize_item_dict({
            "file": "src/a.py",
            "issue": "Missing validation for phase dependencies.",
            "severity": "High",
        })
        assert normalized["description"] == (
            "Missing validation for phase dependencies."
        )
        assert normalized["severity"] == "major"
        assert normalized["suggested_fix"] != ""
        assert normalized["current_code"] == ""

    def test_high_severity_maps_to_major(self) -> None:
        normalized = ReviewResponseParser._normalize_item_dict({
            "file": "a.py", "issue": "x", "severity": "High",
        })
        assert normalized["severity"] == "major"

    def test_medium_severity_maps_to_minor(self) -> None:
        normalized = ReviewResponseParser._normalize_item_dict({
            "file": "a.py", "issue": "x", "severity": "medium",
        })
        assert normalized["severity"] == "minor"
