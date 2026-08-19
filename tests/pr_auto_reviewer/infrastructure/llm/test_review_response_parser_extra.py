"""Extended behavioral tests for ReviewResponseParser covering prose/JSON branches."""

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)


class TestJsonHelpers:
    """Exercises JSON discovery and sanitization helpers."""

    def test_extract_outermost_json_when_balanced_then_extracts(self) -> None:
        text = 'preamble {"a": {"b": 1}} trailing'

        assert ReviewResponseParser.extract_outermost_json(text) == '{"a": {"b": 1}}'

    def test_extract_outermost_json_when_no_braces_then_none(self) -> None:
        assert ReviewResponseParser.extract_outermost_json("plain text") is None

    def test_extract_outermost_json_when_unclosed_then_none(self) -> None:
        assert ReviewResponseParser.extract_outermost_json('{"a": 1') is None

    def test_sanitize_json_literals_when_control_chars_then_escaped(self) -> None:
        raw = '{"desc": "line1\nline2\ttab"}'

        cleaned = ReviewResponseParser._sanitize_json_literals(raw)

        assert "\\n" in cleaned
        assert "\\t" in cleaned
        assert json_loads(cleaned)["desc"] == "line1\nline2\ttab"

    def test_sanitize_json_literals_when_escapes_preserved(self) -> None:
        raw = '{"desc": "already \\"quoted\\""}'

        assert ReviewResponseParser._sanitize_json_literals(raw) == raw

    def test_normalize_item_dict_when_high_severity_then_major(self) -> None:
        item = ReviewResponseParser._normalize_item_dict(
            {"file": "a.py", "severity": "high", "category": "bug", "description": "d"}
        )

        assert item["severity"] == "major"
        assert item["category"] == "bug"

    def test_normalize_item_dict_when_type_key_then_category(self) -> None:
        item = ReviewResponseParser._normalize_item_dict(
            {"file": "a.py", "type": "security", "description": "d"}
        )

        assert item["category"] == "security"

    def test_normalize_item_dict_when_unknown_category_then_default(self) -> None:
        item = ReviewResponseParser._normalize_item_dict(
            {"file": "a.py", "category": "weird", "description": "d"}
        )

        assert item["category"] == "maintainability"

    def test_normalize_item_dict_when_no_fix_then_synthesized(self) -> None:
        item = ReviewResponseParser._normalize_item_dict(
            {"file": "a.py", "description": "found a bug"}
        )

        assert "found a bug" in item["suggested_fix"]

    def test_normalize_item_dict_when_issue_title_message_then_description(self) -> None:
        item = ReviewResponseParser._normalize_item_dict(
            {"issue": "issue text", "title": "title text", "message": "msg"}
        )

        assert item["description"] == "issue text"

    def test_normalize_item_dict_when_code_aliases_then_mapped(self) -> None:
        item = ReviewResponseParser._normalize_item_dict(
            {"file_path": "b.py", "code": "x", "fix": "y", "description": "d"}
        )

        assert item["file"] == "b.py"
        assert item["current_code"] == "x"
        assert item["suggested_fix"] == "y"

    def test_is_concrete_when_both_then_true(self) -> None:
        assert ReviewResponseParser._is_concrete({"current_code": "x", "suggested_fix": "y"}) is True

    def test_is_concrete_when_missing_fix_then_false(self) -> None:
        assert ReviewResponseParser._is_concrete({"current_code": "x"}) is False

    def test_find_items_when_direct_then_found(self) -> None:
        data = {"items": [{"file": "a.py"}, "skip-me"]}

        result = ReviewResponseParser._find_items_in_dict(data)

        assert result == [{"file": "a.py"}]

    def test_find_items_when_nested_dict_then_found(self) -> None:
        data = {"top": {"deep": {"findings": [{"file": "a.py"}]}}}

        assert ReviewResponseParser._find_items_in_dict(data) == [{"file": "a.py"}]

    def test_find_items_when_nested_list_then_found(self) -> None:
        data = {"top": [{"issues": [{"file": "a.py"}]}]}

        assert ReviewResponseParser._find_items_in_dict(data) == [{"file": "a.py"}]

    def test_find_items_when_none_then_empty(self) -> None:
        assert ReviewResponseParser._find_items_in_dict({"top": "x"}) == []


class TestInference:
    """Exercises severity and category inference."""

    def test_infer_severity_when_security_then_critical(self) -> None:
        assert ReviewResponseParser._infer_severity("sql injection risk") == (
            ItemSeverity.CRITICAL,
            "critical",
        )

    def test_infer_severity_when_crash_then_major(self) -> None:
        assert ReviewResponseParser._infer_severity("can cause a crash") == (
            ItemSeverity.MAJOR,
            "major",
        )

    def test_infer_severity_when_typo_then_info(self) -> None:
        assert ReviewResponseParser._infer_severity("typo in comment") == (
            ItemSeverity.INFO,
            "info",
        )

    def test_infer_severity_when_other_then_minor(self) -> None:
        severity, mapped = ReviewResponseParser._infer_severity("minor improvement")

        assert severity == ItemSeverity.MINOR
        assert mapped == "medium"

    def test_infer_type_when_security_then_security(self) -> None:
        assert ReviewResponseParser._infer_type("hardcoded secret", "major") == "security"

    def test_infer_type_when_architecture_then_design(self) -> None:
        assert ReviewResponseParser._infer_type("violates hexagonal boundaries", "major") == "design"

    def test_infer_type_when_test_then_test(self) -> None:
        assert ReviewResponseParser._infer_type("missing unit test", "minor") == "test"

    def test_infer_type_when_convention_then_maintainability(self) -> None:
        assert ReviewResponseParser._infer_type("naming convention", "minor") == "maintainability"

    def test_infer_type_when_critical_severity_then_bug(self) -> None:
        assert ReviewResponseParser._infer_type("unexpected behavior", "critical") == "bug"

    def test_infer_type_when_other_then_quality(self) -> None:
        assert ReviewResponseParser._infer_type("could be clearer", "minor") == "quality"


class TestVerdictResolution:
    """Exercises verdict extraction and resolution."""

    def test_extract_verdict_md_when_heading_changes_then_changes_requested(self) -> None:
        assert (
            ReviewResponseParser._extract_verdict_md("## Verdict\nchanges_requested")
            == ReviewVerdict.CHANGES_REQUESTED
        )

    def test_extract_verdict_md_when_bold_approve_then_approved(self) -> None:
        assert (
            ReviewResponseParser._extract_verdict_md("**Verdict:** approve")
            == ReviewVerdict.APPROVED
        )

    def test_extract_verdict_md_when_bold_commented_then_commented(self) -> None:
        assert (
            ReviewResponseParser._extract_verdict_md("**Verdict:** **commented**")
            == ReviewVerdict.COMMENTED
        )

    def test_extract_verdict_md_when_plain_approve_then_approved(self) -> None:
        assert (
            ReviewResponseParser._extract_verdict_md("Verdict: approve")
            == ReviewVerdict.APPROVED
        )

    def test_extract_verdict_md_when_absent_then_commented(self) -> None:
        assert (
            ReviewResponseParser._extract_verdict_md("nothing here")
            == ReviewVerdict.COMMENTED
        )

    def test_resolve_verdict_when_request_changes_then_cr(self) -> None:
        assert (
            ReviewResponseParser._resolve_verdict("request changes", [])
            == ReviewVerdict.CHANGES_REQUESTED
        )

    def test_resolve_verdict_when_explicit_value_then_parsed(self) -> None:
        assert (
            ReviewResponseParser._resolve_verdict("approved", [])
            == ReviewVerdict.APPROVED
        )

    def test_resolve_verdict_when_enum_value_then_kept(self) -> None:
        assert (
            ReviewResponseParser._resolve_verdict("commented", [])
            == ReviewVerdict.COMMENTED
        )

    def test_resolve_verdict_when_item_blocking_then_cr(self) -> None:
        item = ReviewItem(
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.MAINTAINABILITY,
            file_path="a.py",
            description="d",
            id="ab12",
        )
        assert (
            ReviewResponseParser._resolve_verdict(None, [item])
            == ReviewVerdict.CHANGES_REQUESTED
        )

    def test_determine_verdict_when_any_items_then_changes_requested(self) -> None:
        item = ReviewItem(
            severity=ItemSeverity.INFO,
            category=IssueCategory.MAINTAINABILITY,
            file_path="a.py",
            description="d",
            id="ab12",
        )
        assert ReviewResponseParser._determine_verdict([item]) == ReviewVerdict.CHANGES_REQUESTED

    def test_determine_verdict_when_no_items_then_commented(self) -> None:
        assert ReviewResponseParser._determine_verdict([]) == ReviewVerdict.COMMENTED

    def test_resolve_reason_when_string_then_returned(self) -> None:
        assert ReviewResponseParser._resolve_reason({"reason": "because"}) == "because"

    def test_resolve_reason_when_list_then_joined(self) -> None:
        assert ReviewResponseParser._resolve_reason({"reasons": ["a", "b"]}) == "a b"

    def test_resolve_reason_when_string_reasons_then_returned(self) -> None:
        assert ReviewResponseParser._resolve_reason({"reasons": "single"}) == "single"

    def test_resolve_reason_when_missing_then_empty(self) -> None:
        assert ReviewResponseParser._resolve_reason({}) == ""


class TestMarkdownExtraction:
    """Exercises markdown section extraction helpers."""

    def test_extract_summary_when_section_then_text(self) -> None:
        assert (
            ReviewResponseParser._extract_summary_md("## Summary\noverview text")
            == "overview text"
        )

    def test_extract_summary_when_absent_then_empty(self) -> None:
        assert ReviewResponseParser._extract_summary_md("no summary") == ""

    def test_extract_reason_when_bold_then_text(self) -> None:
        assert (
            ReviewResponseParser._extract_reason_md("**Reason:** alpha")
            == "alpha"
        )

    def test_extract_reason_when_plain_then_text(self) -> None:
        assert ReviewResponseParser._extract_reason_md("Reason: beta") == "beta"

    def test_extract_reason_when_absent_then_empty(self) -> None:
        assert ReviewResponseParser._extract_reason_md("nothing") == ""

    def test_extract_first_paragraph_when_long_then_returned(self) -> None:
        text = "A sufficiently long opening paragraph about the change.\n## Verdict\nx"

        assert ReviewResponseParser._extract_first_paragraph(text) is not None

    def test_extract_first_paragraph_when_verdict_preamble_then_none(self) -> None:
        text = "verdict approved\n## Summary\nx"

        assert ReviewResponseParser._extract_first_paragraph(text) is None

    def test_extract_first_paragraph_when_short_then_none(self) -> None:
        assert ReviewResponseParser._extract_first_paragraph("short\n## Verdict\nx") is None

    def test_extract_first_paragraph_when_absent_then_none(self) -> None:
        assert ReviewResponseParser._extract_first_paragraph("plain") is None

    def test_extract_line_range_when_range_then_dash_form(self) -> None:
        assert ReviewResponseParser._extract_line_range("lines 5-10") == "5-10"

    def test_extract_line_range_when_to_form_then_dash(self) -> None:
        assert ReviewResponseParser._extract_line_range("5 to 10") == "5-10"

    def test_extract_line_range_when_file_line_then_single(self) -> None:
        assert ReviewResponseParser._extract_line_range("src/app.py:12") == "12"

    def test_extract_line_range_when_absent_then_empty(self) -> None:
        assert ReviewResponseParser._extract_line_range("no reference") == ""


class TestProseParsing:
    """Exercises prose/markdown item, suggestion, and praise parsing."""

    def test_parse_markdown_items_when_bullets_then_review_items(self) -> None:
        content = "- [major] bug (src/a.py) Unused import\n- [minor] style (src/b.py) Trailing space"

        items = ReviewResponseParser._parse_markdown_items(content)

        assert len(items) == 2
        assert items[0].file_path == "src/a.py"
        assert items[0].severity == ItemSeverity.MAJOR

    def test_parse_structured_items_when_code_blocks_then_concrete(self) -> None:
        content = (
            "### [major] [bug] src/app.py:12 — unclosed resource\n\n"
            "```python\nf = open(\"x\")\n```\n\n"
            "**Fix:**\n```python\nwith open(\"x\") as fh:\n    pass\n```\n"
        )

        items = ReviewResponseParser._parse_structured_items(content)

        assert len(items) == 1
        assert items[0]["file"] == "src/app.py"
        assert items[0]["line"] == "12"
        assert items[0]["current_code"] == "f = open(\"x\")"
        assert "with open" in items[0]["suggested_fix"]

    def test_parse_structured_items_when_fix_header_then_fix(self) -> None:
        content = (
            "### [minor] [style] src/a.py — long line\n\n"
            "```python\nx = 1\n```\n\n"
            "**Suggested Fix:**\n```python\ny = 2\n```\n"
        )

        items = ReviewResponseParser._parse_structured_items(content)

        assert items[0]["suggested_fix"] == "y = 2"

    def test_only_concrete_when_mixed_then_filters(self) -> None:
        items = [
            {"current_code": "a", "suggested_fix": "b"},
            {"current_code": "c", "suggested_fix": ""},
            {"current_code": "", "suggested_fix": "d"},
        ]

        result = ReviewResponseParser._only_concrete(items)

        assert len(result) == 1

    def test_parse_prose_items_when_issues_section_then_items(self) -> None:
        content = _prose_issues_content()

        items = ReviewResponseParser._parse_prose_items(content)

        assert len(items) == 2
        assert all(item["current_code"] for item in items)
        assert all(item["suggested_fix"] for item in items)

    def test_parse_flat_prose_items_when_headings_then_items(self) -> None:
        content = _prose_flat_content()

        items = ReviewResponseParser._parse_flat_prose_items(content)

        assert len(items) == 2

    def test_parse_recommendations_when_numbered_then_suggestions(self) -> None:
        content = (
            "### Recommendations\n\n"
            "1. Add type hints to src/run.py\n\n"
            "   Introduce return annotations for clarity.\n\n"
            "2. Extract duplicate queries\n\n"
            "   Centralize repeated database access.\n"
        )

        result = ReviewResponseParser.parse_prose_recommendations(content)

        assert len(result) >= 2
        assert result[0]["description"].startswith("Add type hints")

    def test_parse_recommendations_when_backtick_path_then_file(self) -> None:
        content = (
            "### Recommendations\n\n"
            "1. Move constant to `src/config.py`\n\n"
            "   The value is duplicated in three places.\n"
        )

        result = ReviewResponseParser.parse_prose_recommendations(content)

        assert result[0]["file"] == "src/config.py"

    def test_parse_recommendations_when_no_section_then_empty(self) -> None:
        assert ReviewResponseParser.parse_prose_recommendations("nothing") == []

    def test_parse_praise_when_strengths_then_entries(self) -> None:
        content = (
            "### Strengths\n\n"
            "1. Clear error handling\n\n"
            "   The controller centralizes exceptions.\n\n"
            "## Praise\n\n"
            "- Great test coverage\n"
        )

        result = ReviewResponseParser.parse_prose_praise(content)

        assert any("Clear error handling" in e["description"] for e in result)
        assert any(e["description"] == "Great test coverage" for e in result)

    def test_parse_praise_when_none_then_empty(self) -> None:
        assert ReviewResponseParser.parse_prose_praise("nothing") == []

    def test_parse_md_suggestion_line_when_file_then_fields(self) -> None:
        entry = ReviewResponseParser._parse_md_suggestion_line("- src/a.py: Reuse helper")

        assert entry == {"file": "src/a.py:", "line": "", "description": "Reuse helper"}

    def test_parse_md_suggestion_line_when_plain_then_text(self) -> None:
        entry = ReviewResponseParser._parse_md_suggestion_line("- Just a thought")

        assert entry == {"file": "", "line": "", "description": "Just a thought"}

    def test_parse_md_suggestion_line_when_none_marker_then_none(self) -> None:
        assert ReviewResponseParser._parse_md_suggestion_line("- No suggestions") is None

    def test_parse_md_suggestion_line_when_unparsable_then_none(self) -> None:
        assert ReviewResponseParser._parse_md_suggestion_line("plain text") is None

    def test_parse_md_suggestion_line_when_empty_then_none(self) -> None:
        assert ReviewResponseParser._parse_md_suggestion_line("-  ") is None

    def test_parse_md_praise_line_when_file_then_fields(self) -> None:
        entry = ReviewResponseParser._parse_md_praise_line("- src/a.py: solid design")

        assert entry == {"file": "src/a.py", "description": "solid design"}

    def test_parse_md_praise_line_when_plain_then_text(self) -> None:
        entry = ReviewResponseParser._parse_md_praise_line("- nice naming")

        assert entry == {"file": "", "description": "nice naming"}

    def test_parse_md_praise_line_when_none_then_none(self) -> None:
        assert ReviewResponseParser._parse_md_praise_line("- none") is None

    def test_parse_md_praise_line_when_unparsable_then_none(self) -> None:
        assert ReviewResponseParser._parse_md_praise_line("not a bullet") is None

    def test_extract_suggestions_md_when_section_then_entries(self) -> None:
        content = "## Suggestions\n- src/a.py: Reuse helper\n- Second thought\n"

        result = ReviewResponseParser._extract_suggestions_md(content)

        assert len(result) == 2

    def test_extract_suggestions_md_when_absent_then_empty(self) -> None:
        assert ReviewResponseParser._extract_suggestions_md("none") == []

    def test_extract_praise_md_when_section_then_entries(self) -> None:
        content = "## Praise\n- Great coverage\n- Clean code\n"

        result = ReviewResponseParser._extract_praise_md(content)

        assert len(result) == 2

    def test_extract_praise_md_when_absent_then_empty(self) -> None:
        assert ReviewResponseParser._extract_praise_md("none") == []

    def test_strip_frontmatter_when_present_then_removed(self) -> None:
        text = "---\nmodel: x\n---\n## Verdict\napproved"

        assert ReviewResponseParser.strip_frontmatter(text) == "## Verdict\napproved"

    def test_strip_frontmatter_when_absent_then_unchanged(self) -> None:
        assert ReviewResponseParser.strip_frontmatter("plain") == "plain"

    def test_strip_frontmatter_when_single_delimiter_then_stripped_text(self) -> None:
        assert ReviewResponseParser.strip_frontmatter("---\nmodel: x\n") == "---\nmodel: x"


class TestItemDictExtraction:
    """Exercises item-dict extraction and the parse_items pipeline."""

    def test_extract_item_dicts_when_json_block_then_normalized(self) -> None:
        raw = '```json\n{"items": [{"file": "a.py", "severity": "high", "description": "d"}]}\n```'

        result = ReviewResponseParser._extract_item_dicts(raw)

        assert result[0]["severity"] == "major"

    def test_extract_item_dicts_when_nested_then_found(self) -> None:
        raw = '{"top": {"issues": [{"file": "a.py", "description": "d"}]}}'

        result = ReviewResponseParser._extract_item_dicts(raw)

        assert result[0]["file"] == "a.py"

    def test_extract_item_dicts_when_list_then_normalized(self) -> None:
        raw = '[{"file": "a.py", "severity": "low", "description": "d"}]'

        result = ReviewResponseParser._extract_item_dicts(raw)

        assert result[0]["severity"] == "minor"

    def test_extract_item_dicts_when_invalid_then_empty(self) -> None:
        assert ReviewResponseParser._extract_item_dicts("not json at all") == []

    def test_parse_items_when_json_list_then_concrete(self) -> None:
        raw = '[{"file": "a.py", "severity": "major", "description": "d", "current_code": "x", "suggested_fix": "y"}]'

        result = ReviewResponseParser.parse_items(raw)

        assert result[0]["file"] == "a.py"

    def test_parse_items_when_nested_dict_then_concrete(self) -> None:
        raw = '{"analysis": {"findings": [{"file": "a.py", "description": "d", "current_code": "x", "suggested_fix": "y"}]}}'

        result = ReviewResponseParser.parse_items(raw)

        assert result[0]["file"] == "a.py"

    def test_parse_items_when_outermost_json_then_concrete(self) -> None:
        raw = 'preamble text {"items": [{"file": "a.py", "description": "d", "current_code": "x", "suggested_fix": "y"}]} tail'

        result = ReviewResponseParser.parse_items(raw)

        assert result[0]["file"] == "a.py"

    def test_parse_items_when_markdown_bullets_then_items(self) -> None:
        raw = "- [major] bug (src/a.py) Unused import"

        result = ReviewResponseParser.parse_items(raw)

        assert result[0]["file"] == "src/a.py"

    def test_parse_items_when_prose_section_then_items(self) -> None:
        result = ReviewResponseParser.parse_items(_prose_issues_content())

        assert len(result) == 2

    def test_parse_items_when_unparsable_then_empty(self) -> None:
        assert ReviewResponseParser.parse_items("*?* unparseable garbage") == []

    def test_parse_item_observations_when_fixless_then_observations(self) -> None:
        raw = '{"items": [{"file": "a.py", "current_code": "x"}]}'

        result = ReviewResponseParser.parse_item_observations(raw)

        assert result == [{"file": "a.py", "line": "", "description": "Review the identified concern."}]

    def test_parse_item_observations_when_concrete_then_skipped(self) -> None:
        raw = '{"items": [{"file": "a.py", "description": "d", "current_code": "x", "suggested_fix": "y"}]}'

        assert ReviewResponseParser.parse_item_observations(raw) == []


class TestParseTopLevel:
    """Exercises the public parse() entry point end to end."""

    def test_parse_when_json_with_stop_token_then_parsed(self) -> None:
        raw = '{"verdict": "approved", "reason": "r", "summary": "s"}<|im_end|>'

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.APPROVED

    def test_parse_when_json_in_code_block_then_parsed(self) -> None:
        raw = '```json\n{"verdict": "commented", "summary": "ok"}\n```'

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.COMMENTED

    def test_parse_when_embedded_json_then_extracted(self) -> None:
        raw = 'note {"verdict": "approved", "summary": "fine"} note'

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.APPROVED

    def test_parse_when_json_items_infer_fields(self) -> None:
        raw = (
            '{"verdict": "changes_requested", "items": ['
            '{"file": "a.py", "description": {"issue": "unused var"}, "severity": "high"}]}'
        )

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert result.items[0].file_path == "a.py"
        assert "issue=unused var" in result.items[0].description

    def test_parse_when_json_item_missing_file_and_desc_then_skipped(self) -> None:
        raw = '{"verdict": "commented", "items": [{"severity": "info"}]}'

        result = ReviewResponseParser().parse(raw, "m")

        assert result.items == []

    def test_parse_when_json_suggestions_mixed_then_parsed(self) -> None:
        raw = (
            '{"verdict": "commented", "suggestions": ["textual", '
            '{"description": "desc", "file": "a.py", "line": "3", "current_code": "x", "suggested_code": "y"}]}'
        )

        result = ReviewResponseParser().parse(raw, "m")

        assert len(result.suggestions) == 2
        assert result.suggestions[1].file_path == "a.py"

    def test_parse_when_json_praise_mixed_then_parsed(self) -> None:
        raw = '{"verdict": "commented", "praise": ["textual", {"description": "desc", "file": "a.py"}]}'

        result = ReviewResponseParser().parse(raw, "m")

        assert len(result.praise) == 2
        assert result.praise[1].file_path == "a.py"

    def test_clean_response_when_stop_token_then_truncated(self) -> None:
        parser = ReviewResponseParser()

        cleaned = parser._clean_response('{"a": 1}<|im_end|>rest')

        assert cleaned == '{"a": 1}'

    def test_clean_response_when_code_block_then_inner(self) -> None:
        parser = ReviewResponseParser()

        cleaned = parser._clean_response('```json\n{"a": 1}\n```')

        assert cleaned == '{"a": 1}'


def _prose_issues_content() -> str:
    return (
        "### Issues\n\n"
        "1. Unused import in src/main.py\n\n"
        "The `os` module is imported but never referenced.\n\n"
        "**Current Code:**\n```python\nimport os\n```\n\n"
        "**Fix:**\n```python\nimport sys\n```\n\n"
        "2. Magic number in config.py\n\n"
        "The timeout value is a raw literal.\n\n"
        "**Current Code:**\n```python\ntimeout = 30\n```\n\n"
        "**Fix:**\n```python\ntimeout = TIMEOUT_SECONDS\n```\n"
    )


def _prose_flat_content() -> str:
    return (
        "#### 1. Unused import in src/main.py\n\n"
        "The `os` module is imported but never referenced.\n\n"
        "**Current Code:**\n```python\nimport os\n```\n\n"
        "**Fix:**\n```python\nimport sys\n```\n\n"
        "#### 2. Magic number in config.py\n\n"
        "The timeout value is a raw literal.\n\n"
        "**Current Code:**\n```python\ntimeout = 30\n```\n\n"
        "**Fix:**\n```python\ntimeout = TIMEOUT_SECONDS\n```\n"
    )


def json_loads(text: str) -> dict:
    import json

    return json.loads(text)