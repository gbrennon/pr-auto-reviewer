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
                 "description": "bad"},
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
                 "description": "bug"},
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
