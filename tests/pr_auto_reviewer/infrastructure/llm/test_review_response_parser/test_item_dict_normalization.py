from ._helpers import *


class TestItemDictNormalization:
    """LLM items using ``issue``/``severity`` keys must survive parsing."""

    def test_issue_key_maps_to_description_and_suggested_fix(self) -> None:
        normalized = ReviewResponseParser.normalize_item_dict({
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
        normalized = ReviewResponseParser.normalize_item_dict({
            "file": "a.py", "issue": "x", "severity": "High",
        })
        assert normalized["severity"] == "major"

    def test_medium_severity_maps_to_minor(self) -> None:
        normalized = ReviewResponseParser.normalize_item_dict({
            "file": "a.py", "issue": "x", "severity": "medium",
        })
        assert normalized["severity"] == "minor"

