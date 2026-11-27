from ._helpers import *


class TestItemDictNormalization:
    """LLM item aliases normalize without fabricating evidence."""

    def test_issue_key_maps_to_description_without_synthetic_fix(self) -> None:
        normalized = ReviewResponseParser.normalize_item_dict({
            "file": "src/a.py",
            "issue": "Missing validation for phase dependencies.",
            "severity": "High",
            "category": "quality",
        })
        assert normalized["description"] == (
            "Missing validation for phase dependencies."
        )
        assert normalized["severity"] == "major"
        assert normalized["suggested_fix"] == ""
        assert normalized["current_code"] == ""

    def test_high_severity_maps_to_major(self) -> None:
        normalized = ReviewResponseParser.normalize_item_dict({
            "file": "a.py", "issue": "x", "severity": "High", "category": "bug",
        })
        assert normalized["severity"] == "major"

    def test_medium_and_low_severity_map_to_minor(self) -> None:
        for severity in ("medium", "low"):
            normalized = ReviewResponseParser.normalize_item_dict({
                "file": "a.py",
                "issue": "x",
                "severity": severity,
                "category": "bug",
            })
            assert normalized["severity"] == "minor"

    @pytest.mark.parametrize(
        "item",
        [
            {"description": "x", "category": "bug"},
            {"description": "x", "severity": "major"},
            {"severity": "major", "category": "bug"},
            {"description": "x", "severity": "bogus", "category": "bug"},
            {"description": "x", "severity": "major", "category": "bogus"},
        ],
    )
    def test_missing_or_invalid_required_field_is_rejected(self, item) -> None:
        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser.normalize_item_dict(item)

    def test_explicit_empty_fix_is_preserved(self) -> None:
        normalized = ReviewResponseParser.normalize_item_dict({
            "description": "abstract concern",
            "severity": "minor",
            "category": "quality",
            "suggested_fix": "",
        })
        assert normalized["suggested_fix"] == ""

