import json
import pytest
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.entities.review_item import ReviewItem

FIXTURES = "tests/fixtures"


class TestReviewResponseParser:

    def _load(self, name):
        with open(f"{FIXTURES}/ollama_responses/{name}") as f:
            return f.read()

    def test_parse_plain_json_returns_code_review(self):
        raw = self._load("plain_json.json")
        result = ReviewResponseParser.parse(raw, "test-model")
        assert isinstance(result, CodeReview)

    def test_parse_plain_json_extracts_summary(self):
        raw = self._load("plain_json.json")
        result = ReviewResponseParser.parse(raw, "test-model")
        assert result.summary == "Test summary"

    def test_parse_plain_json_extracts_issue(self):
        raw = self._load("plain_json.json")
        result = ReviewResponseParser.parse(raw, "test-model")
        assert len(result.items) == 1
        assert result.items[0].file_path == "foo.py"
        assert result.items[0].description == "test issue"

    def test_parse_plain_json_high_severity_is_changes_requested(self):
        raw = self._load("plain_json.json")
        result = ReviewResponseParser.parse(raw, "test-model")
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_parse_plain_json_sets_model_used(self):
        raw = self._load("plain_json.json")
        result = ReviewResponseParser.parse(raw, "test-model")
        assert result.model_used == "test-model"

    def test_parse_code_block_extracts_issues(self):
        raw = self._load("code_block.txt")
        result = ReviewResponseParser.parse(raw, "m")
        assert len(result.items) == 1
        assert result.items[0].file_path == "foo.py"

    def test_parse_invalid_json_falls_back_to_markdown(self):
        raw = self._load("invalid_json.txt")
        result = ReviewResponseParser.parse(raw, "m")
        assert isinstance(result, CodeReview)
        assert result.summary == "OOPS: model failed to produce JSON"

    def test_parse_empty_response_returns_comment_verdict(self):
        raw = self._load("empty_response.json")
        result = ReviewResponseParser.parse(raw, "m")
        assert isinstance(result, CodeReview)

    def test_parse_json_with_critical_issue_returns_changes_requested(self):
        data = {
            "issues": [
                {"file": "x.py", "line": "1",
                 "severity": "critical", "type": "security",
                 "description": "bad",
                 "current_code": "+ password = request.args['password']",
                 "suggested_fix": "password = request.form['password']"},
            ],
            "summary": "x",
        }
        raw = json.dumps(data)
        result = ReviewResponseParser.parse(raw, "m")
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_parse_json_without_issues_returns_approved(self):
        data = {"issues": [], "summary": "ok"}
        raw = json.dumps(data)
        result = ReviewResponseParser.parse(raw, "m")
        assert result.verdict == ReviewVerdict.APPROVED

    def test_parse_json_with_info_only_returns_approved(self):
        data = {
            "issues": [
                {"file": "x.py", "line": "1",
                 "severity": "low", "type": "quality",
                 "description": "minor"},
            ],
            "summary": "ok",
        }
        raw = json.dumps(data)
        result = ReviewResponseParser.parse(raw, "m")
        assert result.verdict == ReviewVerdict.APPROVED

    def test_parse_json_drops_issue_without_concrete_code(self):
        data = {
            "issues": [
                {"file": "x.py", "line": "1",
                 "severity": "medium", "type": "quality",
                 "description": "abstract issue"},
            ],
            "summary": "ok",
        }
        raw = json.dumps(data)
        result = ReviewResponseParser.parse(raw, "m")
        assert result.items == []

    def test_parse_json_drops_issue_without_file_path(self):
        data = {
            "issues": [
                {"line": "1", "severity": "medium", "type": "quality",
                 "description": "missing file",
                 "current_code": "x = 1",
                 "suggested_fix": "x = 2"},
            ],
            "summary": "ok",
        }
        raw = json.dumps(data)
        result = ReviewResponseParser.parse(raw, "m")
        assert result.items == []

    def test_parse_json_ignores_file_summary_changes_key(self):
        data = {
            "changes": [
                {"file": "x.py", "description": "Added logging"},
            ],
            "summary": "ok",
        }
        raw = json.dumps(data)
        result = ReviewResponseParser.parse(raw, "m")
        assert result.items == []

    def test_parse_markdown_format_extracts_verdict(self):
        raw = (
            "## Verdict\nchanges_requested\n\n"
            "## Summary\nSecurity concerns.\n\n"
            "## Items\nNone"
        )
        result = ReviewResponseParser.parse(raw, "m")
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_parse_markdown_format_extracts_summary(self):
        raw = (
            "## Verdict\napproved\n\n"
            "## Summary\nLooks good.\n\n"
            "## Items\nNone"
        )
        result = ReviewResponseParser.parse(raw, "m")
        assert result.summary == "Looks good."

    def test_parse_markdown_approved_verdict(self):
        raw = "## Verdict\napproved\n\n## Summary\nok\n\n## Items\nNone"
        result = ReviewResponseParser.parse(raw, "m")
        assert result.verdict == ReviewVerdict.APPROVED

    def test_parse_markdown_items_with_severity_and_file(self):
        raw = (
            "## Verdict\nchanges_requested\n\n"
            "## Summary\nIssues found.\n\n"
            "## Items\n"
            "- [major] security (src/auth.py) Missing password hashing\n"
        )
        result = ReviewResponseParser.parse(raw, "m")
        assert len(result.items) == 1
        assert result.items[0].file_path == "src/auth.py"
        assert result.items[0].category == "security"

    def test_parse_response_with_response_field_does_not_crash(self):
        raw = self._load("response_with_response_field.json")
        result = ReviewResponseParser.parse(raw, "m")
        assert isinstance(result, CodeReview)

    def test_parse_with_suggestions_preserves_item_count(self):
        data = {
            "issues": [
                {"file": "a.py", "line": "1",
                 "severity": "medium", "type": "bug",
                 "description": "bug",
                 "current_code": "+ value = data['value']",
                 "suggested_fix": "value = data.get('value')"},
            ],
            "suggestions": [
                {"file": "b.py", "line": "2",
                 "description": "improvement"},
            ],
            "summary": "ok",
        }
        raw = json.dumps(data)
        result = ReviewResponseParser.parse(raw, "m")
        assert len(result.items) == 1

    def test_parse_when_nested_json_embedded_in_text_then_extracts_and_parses(self):
        raw = 'Some preamble text.\\n{"issues":[],"summary":"nested ok","verdict":"approved"}\\nMore text after.'
        result = ReviewResponseParser.parse(raw, "m")
        assert result.verdict == ReviewVerdict.APPROVED
        assert result.summary == "nested ok"

    def test_parse_when_no_json_and_no_markdown_then_extracts_first_paragraph(self):
        raw = "This is a nice PR that improves code quality significantly. It adds tests and refactors modules."
        result = ReviewResponseParser.parse(raw, "m")
        assert "This is a nice PR" in result.summary

    def test_parse_when_no_json_and_no_markdown_and_short_text_then_uses_raw(self):
        raw = "ok"
        result = ReviewResponseParser.parse(raw, "m")
        assert result.summary == "ok"

    def test_extract_outermost_json_when_no_braces_then_returns_none(self):
        assert ReviewResponseParser._extract_outermost_json("no braces here") is None

    def test_extract_outermost_json_when_nested_braces_then_returns_outermost(self):
        result = ReviewResponseParser._extract_outermost_json('{"a": {"b": 1}}')
        assert result is not None
        assert result.startswith("{")
        assert result.endswith("}")

    def test_resolve_verdict_when_explicit_changes_requested_then_returns_cr(self):
        assert ReviewResponseParser._resolve_verdict("changes_requested", []) == ReviewVerdict.CHANGES_REQUESTED

    def test_resolve_verdict_when_explicit_approved_then_returns_approved(self):
        assert ReviewResponseParser._resolve_verdict("approved", []) == ReviewVerdict.APPROVED

    def test_resolve_verdict_when_explicit_commented_then_returns_commented(self):
        assert ReviewResponseParser._resolve_verdict("commented", []) == ReviewVerdict.COMMENTED

    def test_extract_verdict_md_when_bold_verdict_changes_then_returns_cr(self):
        raw = "**Verdict:** **Request Changes**\\nSome text"
        assert ReviewResponseParser._extract_verdict_md(raw) == ReviewVerdict.CHANGES_REQUESTED

    def test_extract_verdict_md_when_bold_verdict_approved_then_returns_approved(self):
        raw = "**Verdict:** **Approved**\\nSome text"
        assert ReviewResponseParser._extract_verdict_md(raw) == ReviewVerdict.APPROVED

    def test_extract_verdict_md_when_bold_verdict_commented_then_returns_commented(self):
        raw = "**Verdict:** **Commented**\\nSome text"
        assert ReviewResponseParser._extract_verdict_md(raw) == ReviewVerdict.COMMENTED

    def test_extract_verdict_md_when_plain_verdict_changes_then_returns_cr(self):
        raw = "Verdict: changes_requested\\nOther text"
        assert ReviewResponseParser._extract_verdict_md(raw) == ReviewVerdict.CHANGES_REQUESTED

    def test_extract_verdict_md_when_plain_verdict_approved_then_returns_approved(self):
        raw = "Verdict: approved\\nOther text"
        assert ReviewResponseParser._extract_verdict_md(raw) == ReviewVerdict.APPROVED

    def test_extract_first_paragraph_when_starts_with_verdict_then_skips_and_returns_none(self):
        assert ReviewResponseParser._extract_first_paragraph("Verdict: x\\n\\n## Summary\\n...") is None

    def test_extract_first_paragraph_when_bold_verdict_then_skips_and_returns_none(self):
        assert ReviewResponseParser._extract_first_paragraph("**Verdict:** x\\n\\n## Summary\\n...") is None


    def test_parse_when_extracted_json_is_malformed_then_falls_back_to_markdown(self):
        raw = "Some text with { malformed: json } inside\n\n## Verdict\napproved\n\n## Summary\ngood\n\n## Items\nNone"
        result = ReviewResponseParser.parse(raw, "m")
        assert result.verdict == ReviewVerdict.APPROVED
        assert result.summary == "good"

    def test_parse_when_code_block_has_invalid_json_then_falls_back_to_markdown(self):
        raw = "```json\n{not valid json}\n```\n\n## Verdict\napproved\n\n## Summary\nfallback\n\n## Items\nNone"
        result = ReviewResponseParser.parse(raw, "m")
        assert result.verdict == ReviewVerdict.APPROVED
        assert result.summary == "fallback"

    # --- _infer_severity tests -------------------------------------------------

    def test_infer_severity_critical_from_security_keywords(self):
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
        severity, _ = ReviewResponseParser._infer_severity(
            "This has a security vulnerability with injection risk"
        )
        assert severity == ItemSeverity.CRITICAL

    def test_infer_severity_critical_from_leak_keyword(self):
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
        severity, _ = ReviewResponseParser._infer_severity(
            "Memory leak detected in the handler"
        )
        assert severity == ItemSeverity.CRITICAL

    def test_infer_severity_critical_from_hardcoded_keyword(self):
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
        severity, _ = ReviewResponseParser._infer_severity(
            "Hardcoded credentials in config"
        )
        assert severity == ItemSeverity.CRITICAL

    def test_infer_severity_high_from_crash_keyword(self):
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
        severity, _ = ReviewResponseParser._infer_severity(
            "Null pointer dereference causes crash"
        )
        assert severity == ItemSeverity.MAJOR

    def test_infer_severity_high_from_data_loss_keyword(self):
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
        severity, _ = ReviewResponseParser._infer_severity(
            "Potential data loss on unexpected shutdown"
        )
        assert severity == ItemSeverity.MAJOR

    def test_infer_severity_low_from_naming_keyword(self):
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
        severity, _ = ReviewResponseParser._infer_severity(
            "Naming convention should be snake_case"
        )
        assert severity == ItemSeverity.INFO

    def test_infer_severity_low_from_typo_keyword(self):
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
        severity, _ = ReviewResponseParser._infer_severity(
            "Typo in error message text"
        )
        assert severity == ItemSeverity.INFO

    def test_infer_severity_low_from_documentation_keyword(self):
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
        severity, _ = ReviewResponseParser._infer_severity(
            "Update readme with new documentation"
        )
        assert severity == ItemSeverity.INFO

    def test_infer_severity_defaults_to_minor(self):
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
        severity, severity_str = ReviewResponseParser._infer_severity(
            "Some random description with no keywords"
        )
        assert severity == ItemSeverity.MINOR
        assert severity_str == "medium"

    # --- _infer_type tests ----------------------------------------------------

    def test_infer_type_security_from_security_keywords(self):
        t = ReviewResponseParser._infer_type(
            "Security vulnerability via injection", "critical"
        )
        assert t == "security"

    def test_infer_type_security_from_hardcoded(self):
        t = ReviewResponseParser._infer_type(
            "Hardcoded API key found", "high"
        )
        assert t == "security"

    def test_infer_type_architecture_from_layer_keywords(self):
        t = ReviewResponseParser._infer_type(
            "Architecture violation: tight coupling between layers", "high"
        )
        assert t == "design"

    def test_infer_type_architecture_from_hexagonal(self):
        t = ReviewResponseParser._infer_type(
            "Hexagonal port not properly implemented", "high"
        )
        assert t == "design"

    def test_infer_type_solid_from_srp(self):
        t = ReviewResponseParser._infer_type(
            "Single responsibility principle violated", "major"
        )
        assert t == "design"

    def test_infer_type_solid_from_dependency_inversion(self):
        t = ReviewResponseParser._infer_type(
            "Dependency inversion not followed", "major"
        )
        assert t == "design"

    def test_infer_type_test_from_coverage(self):
        t = ReviewResponseParser._infer_type(
            "Missing test coverage for edge case", "minor"
        )
        assert t == "test"

    def test_infer_type_convention_from_formatting(self):
        t = ReviewResponseParser._infer_type(
            "Formatting convention not followed", "low"
        )
        assert t == "maintainability"

    def test_infer_type_quality_from_magic_number(self):
        t = ReviewResponseParser._infer_type(
            "Magic number used without constant", "minor"
        )
        assert t == "maintainability"

    def test_infer_type_quality_from_duplication(self):
        t = ReviewResponseParser._infer_type(
            "Code duplication between modules", "minor"
        )
        assert t == "maintainability"

    def test_infer_type_default_critical_severity_returns_bug(self):
        t = ReviewResponseParser._infer_type(
            "Some issue description", "critical"
        )
        assert t == "bug"

    def test_infer_type_default_high_severity_returns_bug(self):
        t = ReviewResponseParser._infer_type(
            "Some issue description", "high"
        )
        assert t == "bug"

    def test_infer_type_default_low_severity_returns_quality(self):
        t = ReviewResponseParser._infer_type(
            "Some issue description", "low"
        )
        assert t == "quality"


    # --- _extract_suggestions_md tests ----------------------------------------

    def test_extract_suggestions_md_no_section_returns_empty(self):
        result = ReviewResponseParser._extract_suggestions_md(
            "## Verdict\napproved\n\n## Summary\nok\n\n## Items\nNone\n"
        )
        assert result == []

    def test_extract_suggestions_md_numbered_with_file_and_line(self):
        raw = (
            "## Verdict\napproved\n\n"
            "## Summary\nok\n\n"
            "## Items\nNone\n\n"
            "## Suggestions\n"
            "1. a.py: 42 Use a context manager here\n"
            "2. utils.py:10 Extract to a helper function\n"
        )
        result = ReviewResponseParser._extract_suggestions_md(raw)
        assert len(result) == 2
        assert result[0]["file"] == "a.py:"
        assert result[0]["line"] == "42"
        assert "context manager" in result[0]["description"]

    def test_extract_suggestions_md_numbered_no_file(self):
        raw = (
            "## Verdict\napproved\n\n"
            "## Summary\nok\n\n"
            "## Items\nNone\n\n"
            "## Suggestions\n"
            "1. Consider adding more comments throughout\n"
        )
        result = ReviewResponseParser._extract_suggestions_md(raw)
        assert len(result) == 1
        assert "adding more comments" in result[0]["description"]

    def test_extract_suggestions_md_bullet_format(self):
        raw = (
            "## Verdict\napproved\n\n"
            "## Summary\nok\n\n"
            "## Items\nNone\n\n"
            "## Suggestions\n"
            "- Add integration tests\n"
            "* Improve error messages\n"
        )
        result = ReviewResponseParser._extract_suggestions_md(raw)
        assert len(result) == 2
        assert "integration tests" in result[0]["description"]
        assert "error messages" in result[1]["description"]

    def test_extract_suggestions_md_skips_no_suggestion_line(self):
        raw = (
            "## Verdict\napproved\n\n"
            "## Summary\nok\n\n"
            "## Items\nNone\n\n"
            "## Suggestions\n"
            "no suggestions\n"
            "- Actually refactor this module\n"
        )
        result = ReviewResponseParser._extract_suggestions_md(raw)
        assert len(result) == 1
        assert "refactor" in result[0]["description"]

    # --- _extract_praise_md tests ---------------------------------------------

    def test_extract_praise_md_no_section_returns_empty(self):
        result = ReviewResponseParser._extract_praise_md(
            "## Verdict\napproved\n\n## Summary\nok\n\n## Items\nNone\n"
        )
        assert result == []

    def test_extract_praise_md_bullet_with_file_colon_desc(self):
        raw = (
            "## Verdict\napproved\n\n"
            "## Summary\nok\n\n"
            "## Items\nNone\n\n"
            "## Praise\n"
            "- src/auth.py: Good use of hashing\n"
            "* tests/test_auth.py: Comprehensive test coverage\n"
        )
        result = ReviewResponseParser._extract_praise_md(raw)
        assert len(result) == 2
        assert result[0]["file"] == "src/auth.py"
        assert "hashing" in result[0]["description"]
        assert result[1]["file"] == "tests/test_auth.py"
        assert "coverage" in result[1]["description"]

    def test_extract_praise_md_bullet_no_file(self):
        raw = (
            "## Verdict\napproved\n\n"
            "## Summary\nok\n\n"
            "## Items\nNone\n\n"
            "## Praise\n"
            "- Overall clean architecture\n"
        )
        result = ReviewResponseParser._extract_praise_md(raw)
        assert len(result) == 1
        assert "clean architecture" in result[0]["description"]

    def test_extract_praise_md_skips_no_notable_line(self):
        raw = (
            "## Verdict\napproved\n\n"
            "## Summary\nok\n\n"
            "## Items\nNone\n\n"
            "## Praise\n"
            "no notable praise\n"
            "- Good error handling\n"
        )
        result = ReviewResponseParser._extract_praise_md(raw)
        assert len(result) == 1
        assert "error handling" in result[0]["description"]

    # --- parse: reasons field handling ----------------------------------------

    def test_parse_json_with_reasons_list_joins_them(self):
        data = {
            "issues": [{"file": "x.py", "line": "1", "severity": "low",
                        "type": "quality", "description": "minor"}],
            "summary": "ok",
            "reasons": ["First reason", "Second reason"],
        }
        raw = json.dumps(data)
        result = ReviewResponseParser.parse(raw, "m")
        assert "First reason Second reason" == result.reason

    def test_parse_json_with_reasons_string_uses_directly(self):
        data = {
            "issues": [{"file": "x.py", "line": "1", "severity": "low",
                        "type": "quality", "description": "minor"}],
            "summary": "ok",
            "reasons": "Single reason string",
        }
        raw = json.dumps(data)
        result = ReviewResponseParser.parse(raw, "m")
        assert result.reason == "Single reason string"

    # --- parse: unknown severity triggers _infer_severity ---------------------

    def test_parse_json_unknown_severity_triggers_inference(self):
        data = {
            "issues": [
                {"file": "x.py", "line": "1",
                 "severity": "unknown-bogus",
                 "type": "quality",
                 "description": "security vulnerability in auth flow",
                 "current_code": "+ password = request.args['password']",
                 "suggested_fix": "password = request.form['password']"},
            ],
            "summary": "ok",
        }
        raw = json.dumps(data)
        result = ReviewResponseParser.parse(raw, "m")
        from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
        assert result.items[0].severity == ItemSeverity.CRITICAL

    # --- parse: empty type triggers _infer_type -------------------------------

    def test_parse_json_empty_type_triggers_inference(self):
        data = {
            "issues": [
                {"file": "x.py", "line": "1",
                 "severity": "medium",
                 "type": "",
                 "description": "security vulnerability in auth flow",
                 "current_code": "+ password = request.args['password']",
                 "suggested_fix": "password = request.form['password']"},
            ],
            "summary": "ok",
        }
        raw = json.dumps(data)
        result = ReviewResponseParser.parse(raw, "m")
        assert result.items[0].category == "security"

    def test_parse_json_missing_type_triggers_inference(self):
        data = {
            "issues": [
                {"file": "x.py", "line": "1",
                 "severity": "medium",
                 "description": "Naming issue with variable names",
                 "current_code": "+ x = get_value()",
                 "suggested_fix": "value = get_value()"},
            ],
            "summary": "ok",
        }
        raw = json.dumps(data)
        result = ReviewResponseParser.parse(raw, "m")
        assert result.items[0].category == "maintainability"

    # --- _extract_items_md: invalid severity falls back to INFO ---------------
