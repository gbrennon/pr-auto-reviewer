"""Behavioral tests for the infrastructure review-item schemas."""

from pr_auto_reviewer.infrastructure.llm.schemas import ReviewItemSchema


class TestReviewItemSchema:
    """Exercises field coercion and parser-dict construction."""

    def test_defaults_when_empty_then_defaults(self) -> None:
        schema = ReviewItemSchema()

        assert schema.file == ""
        assert schema.severity == "info"
        assert schema.category == "maintainability"
        assert schema.line == ""
        assert schema.description == ""
        assert schema.current_code == ""
        assert schema.suggested_fix == ""

    def test_severity_when_uppercase_then_lowercased(self) -> None:
        assert ReviewItemSchema(severity="MAJOR").severity == "major"

    def test_severity_when_valid_then_preserved(self) -> None:
        assert ReviewItemSchema(severity="critical").severity == "critical"

    def test_severity_when_whitespace_then_stripped(self) -> None:
        assert ReviewItemSchema(severity="  minor  ").severity == "minor"

    def test_severity_when_substring_then_matched(self) -> None:
        assert ReviewItemSchema(severity="critical issue").severity == "critical"

    def test_severity_when_unknown_then_info(self) -> None:
        assert ReviewItemSchema(severity="blah").severity == "info"

    def test_severity_when_non_string_then_info(self) -> None:
        assert ReviewItemSchema.model_validate({"severity": 5}).severity == "info"

    def test_category_when_uppercase_then_lowercased(self) -> None:
        assert ReviewItemSchema(category="SECURITY").category == "security"

    def test_category_when_whitespace_then_stripped(self) -> None:
        assert ReviewItemSchema(category=" bug ").category == "bug"

    def test_category_when_non_string_then_default(self) -> None:
        assert ReviewItemSchema.model_validate({"category": None}).category == "maintainability"

    def test_line_when_none_then_empty(self) -> None:
        assert ReviewItemSchema.model_validate({"line": None}).line == ""

    def test_line_when_int_then_string(self) -> None:
        assert ReviewItemSchema.model_validate({"line": 42}).line == "42"

    def test_line_when_whitespace_then_stripped(self) -> None:
        assert ReviewItemSchema(line=" 12 ").line == "12"

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

    def test_from_parser_dict_when_missing_then_defaults(self) -> None:
        schema = ReviewItemSchema.from_parser_dict({})

        assert schema.file == ""
        assert schema.severity == "info"
        assert schema.category == "maintainability"
        assert schema.line == ""