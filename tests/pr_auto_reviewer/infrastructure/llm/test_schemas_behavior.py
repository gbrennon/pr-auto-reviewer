"""Behavioral tests for the infrastructure review-item schemas."""

import pytest
from pydantic import ValidationError

from pr_auto_reviewer.infrastructure.llm.schemas import ReviewItemSchema


def _schema(**updates: object) -> ReviewItemSchema:
    values: dict[str, object] = {
        "severity": "info",
        "category": "general",
        "description": "description",
    }
    values.update(updates)
    return ReviewItemSchema(**values)


class TestReviewItemSchema:
    def test_empty_payload_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewItemSchema()

    def test_severity_when_uppercase_then_lowercased(self) -> None:
        assert _schema(severity="MAJOR").severity == "major"

    def test_severity_when_valid_then_preserved(self) -> None:
        assert _schema(severity="critical").severity == "critical"

    def test_severity_when_whitespace_then_stripped(self) -> None:
        assert _schema(severity="  minor  ").severity == "minor"

    def test_severity_alias_is_normalized(self) -> None:
        assert _schema(severity="high").severity == "major"

    def test_severity_when_substring_then_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _schema(severity="critical issue")

    def test_severity_when_unknown_then_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _schema(severity="blah")

    def test_severity_when_non_string_then_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _schema(severity=5)

    def test_category_when_uppercase_then_lowercased(self) -> None:
        assert _schema(category="SECURITY").category == "security"

    def test_category_when_whitespace_then_stripped(self) -> None:
        assert _schema(category=" bug ").category == "bug"

    def test_category_alias_is_normalized(self) -> None:
        assert _schema(category="correctness").category == "bug"

    def test_category_when_non_string_then_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _schema(category=None)

    def test_description_when_missing_then_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewItemSchema(severity="info", category="general")

    def test_fileless_item_with_explicit_description_is_valid(self) -> None:
        schema = _schema(file="", suggested_fix="")

        assert schema.file == ""
        assert schema.suggested_fix == ""

    def test_line_when_none_then_empty(self) -> None:
        assert _schema(line=None).line == ""

    def test_line_when_int_then_string(self) -> None:
        assert _schema(line=42).line == "42"

    def test_line_when_whitespace_then_stripped(self) -> None:
        assert _schema(line=" 12 ").line == "12"

    def test_from_parser_dict_when_full_then_maps(self) -> None:
        schema = ReviewItemSchema.from_parser_dict(
            {
                "file": "a.py",
                "severity": "major",
                "category": "bug",
                "description": "d",
                "line": "3",
                "current_code": "x",
                "suggested_fix": "y",
            }
        )

        assert schema.file == "a.py"
        assert schema.severity == "major"
        assert schema.description == "d"
        assert schema.line == "3"
        assert schema.current_code == "x"
        assert schema.suggested_fix == "y"

    def test_from_parser_dict_when_missing_required_fields_then_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewItemSchema.from_parser_dict({})