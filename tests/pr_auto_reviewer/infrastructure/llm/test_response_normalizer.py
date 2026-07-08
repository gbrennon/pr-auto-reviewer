"""Tests for ResponseFieldNormalizer using captured fixtures."""

from pr_auto_reviewer.infrastructure.llm.response_normalizer import (
    ResponseFieldNormalizer,
)
from tests.fixtures.response_normalizer_fixtures import ResponseNormalizerFixtures as F


class TestResponseFieldNormalizer:
    def test_normalize_issue_well_formed(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer.normalize_issue(F.well_formed_issue, 0)
        assert result["file"] == "src/app.py"
        assert result["line"] == "42"
        assert "null check" in result["description"]

    def test_normalize_issue_partial_fields(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer.normalize_issue(F.partial_issue, 3)
        assert result["file"] == "src/utils.py"
        assert result["line"] == ""
        assert "f-string" in result["description"]

    def test_normalize_issue_empty_dict(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer.normalize_issue(F.empty_issue, 0)
        assert result["file"] == "file-0"

    def test_normalize_issue_none_values(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer.normalize_issue(F.none_issue, 1)
        assert result["file"] == "file-1"
        assert result["line"] == ""
        assert result["description"] == ""

    def test_normalize_summary_string(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer.normalize_summary("good review") == "good review"

    def test_normalize_summary_none(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer.normalize_summary(None) == ""

    def test_normalize_verdict_string(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer.normalize_verdict("approved") == "approved"

    def test_normalize_verdict_none(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer.normalize_verdict(None) == ""

    def test_normalize_suggestions(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer.normalize_suggestions(F.suggestions)
        assert len(result) == 2
        assert result[0]["description"] == "Consider using async/await"

    def test_normalize_suggestions_empty(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer.normalize_suggestions([]) == []

    def test_normalize_praise(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer.normalize_praise(F.praise)
        assert len(result) == 2
        assert result[0]["description"] == "Clean separation of concerns"

    def test_normalize_praise_empty(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer.normalize_praise([]) == []

    def test_normalize_reason_string(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer.normalize_reason("needs work") == "needs work"

    def test_normalize_reason_list(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer.normalize_reason(F.reason_list)
        assert "missing error handling" in result
        assert "no input validation" in result

    def test_normalize_reason_none(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer.normalize_reason(None) == ""

    def test_coerce_severity_valid(self):
        normalizer = ResponseFieldNormalizer()
        for s in F.severity_samples:
            result = normalizer._coerce_severity(s)
            assert result in ("critical", "major", "minor", "info", "nitpick")

    def test_coerce_severity_invalid(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._coerce_severity("garbage") == "info"

    def test_coerce_severity_none(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._coerce_severity(None) == "info"

    def test_coerce_category_valid(self):
        normalizer = ResponseFieldNormalizer()
        for c in F.category_samples:
            result = normalizer._coerce_category(c)
            assert result in (
                "bug",
                "security",
                "performance",
                "maintainability",
                "style",
            )

    def test_coerce_category_invalid(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._coerce_category("nonsense") == "general"

    def test_coerce_category_none(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._coerce_category(None) == "general"

    def test_ensure_str_string(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._ensure_str("hello") == "hello"

    def test_ensure_str_none(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._ensure_str(None) == ""

    def test_ensure_str_none_with_default(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._ensure_str(None, "fallback") == "fallback"

    def test_ensure_str_number(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._ensure_str(42) == "42"

    def test_ensure_str_dict(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer._ensure_str(F.ensure_str_dict)
        assert "key=value" in result
        assert "status=error" in result

    def test_ensure_str_list(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer._ensure_str(F.ensure_str_list)
        assert "1" in result
        assert "2" in result
        assert "3" in result

    def test_coerce_description_dict(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer._coerce_description(F.description_dict)
        assert "detail=The function is too long" in result
        assert "line=42" in result

    def test_coerce_description_list(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer._coerce_description(F.description_list)
        assert "Missing null check" in result
        assert "No input validation" in result

    def test_coerce_description_int(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer._coerce_description(F.description_int)
        assert result == "404"

    def test_coerce_severity_high(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._coerce_severity("high") == "major"

    def test_coerce_severity_major_alias(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._coerce_severity("major") == "major"

    def test_coerce_severity_medium(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._coerce_severity("medium") == "minor"

    def test_coerce_severity_low(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._coerce_severity("low") == "info"

    def test_coerce_severity_security_keyword(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._coerce_severity("security_issue") == "critical"

    def test_coerce_severity_critical_keyword(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._coerce_severity("critical_bug") == "critical"

    def test_coerce_category_invalid_value_error(self):
        normalizer = ResponseFieldNormalizer()
        assert normalizer._coerce_category(12345) == "general"

    def test_ensure_str_custom_object(self):
        normalizer = ResponseFieldNormalizer()
        result = normalizer._ensure_str(object())
        assert isinstance(result, str)
