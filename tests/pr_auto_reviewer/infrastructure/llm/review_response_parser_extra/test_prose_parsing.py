from ._helpers import *


class TestProseParsing:
    """Exercises prose/markdown item, suggestion, and praise parsing."""

    def test_parse_markdown_items_when_bullets_then_review_items(self) -> None:
        content = "- [major] bug (src/a.py) Unused import\n- [minor] style (src/b.py) Trailing space"

        items = ReviewResponseParser()._parse_markdown_items(content)

        assert len(items) == 2
        assert items[0].file_path == "src/a.py"
        assert items[0].severity == ItemSeverity.MAJOR

    def test_parse_structured_items_when_code_blocks_then_concrete(self) -> None:
        content = (
            "### [major] [bug] src/app.py:12 — unclosed resource\n\n"
            "```python\nf = open(\"x\")\n```\n\n"
            "**Fix:**\n```python\nwith open(\"x\") as fh:\n    pass\n```\n"
        )

        items = ReviewResponseParser()._parse_structured_items(content)

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

        items = ReviewResponseParser()._parse_structured_items(content)

        assert items[0]["suggested_fix"] == "y = 2"

    def test_only_concrete_when_mixed_then_filters(self) -> None:
        items = [
            {"current_code": "a", "suggested_fix": "b"},
            {"current_code": "c", "suggested_fix": ""},
            {"current_code": "", "suggested_fix": "d"},
        ]

        result = ReviewResponseParser()._only_concrete(items)

        assert len(result) == 1

    def test_parse_prose_items_when_issues_section_then_items(self) -> None:
        content = _prose_issues_content()

        items = ReviewResponseParser()._parse_prose_items(content)

        assert len(items) == 2
        assert all(item["current_code"] for item in items)
        assert all(item["suggested_fix"] for item in items)

    def test_parse_flat_prose_items_when_headings_then_items(self) -> None:
        content = _prose_flat_content()

        items = ReviewResponseParser()._parse_flat_prose_items(content)

        assert len(items) == 2

    def test_parse_recommendations_when_numbered_then_suggestions(self) -> None:
        content = (
            "### Recommendations\n\n"
            "1. Add type hints to src/run.py\n\n"
            "   Introduce return annotations for clarity.\n\n"
            "2. Extract duplicate queries\n\n"
            "   Centralize repeated database access.\n"
        )

        result = ReviewResponseParser().parse_prose_recommendations(content)

        assert len(result) >= 2
        assert result[0]["description"].startswith("Add type hints")

    def test_parse_recommendations_when_backtick_path_then_file(self) -> None:
        content = (
            "### Recommendations\n\n"
            "1. Move constant to `src/config.py`\n\n"
            "   The value is duplicated in three places.\n"
        )

        result = ReviewResponseParser().parse_prose_recommendations(content)

        assert result[0]["file"] == "src/config.py"

    def test_parse_recommendations_when_no_section_then_empty(self) -> None:
        assert ReviewResponseParser().parse_prose_recommendations("nothing") == []

    def test_parse_praise_when_strengths_then_entries(self) -> None:
        content = (
            "### Strengths\n\n"
            "1. Clear error handling\n\n"
            "   The controller centralizes exceptions.\n\n"
            "## Praise\n\n"
            "- Great test coverage\n"
        )

        result = ReviewResponseParser().parse_prose_praise(content)

        assert any("Clear error handling" in e["description"] for e in result)
        assert any(e["description"] == "Great test coverage" for e in result)

    def test_parse_praise_when_none_then_empty(self) -> None:
        assert ReviewResponseParser().parse_prose_praise("nothing") == []

    def test_parse_md_suggestion_line_when_file_then_fields(self) -> None:
        entry = ReviewResponseParser()._parse_md_suggestion_line("- src/a.py: Reuse helper")

        assert entry == {"file": "src/a.py:", "line": "", "description": "Reuse helper"}

    def test_parse_md_suggestion_line_when_plain_then_text(self) -> None:
        entry = ReviewResponseParser()._parse_md_suggestion_line("- Just a thought")

        assert entry == {"file": "", "line": "", "description": "Just a thought"}

    def test_parse_md_suggestion_line_when_none_marker_then_none(self) -> None:
        assert ReviewResponseParser()._parse_md_suggestion_line("- No suggestions") is None

    def test_parse_md_suggestion_line_when_unparsable_then_none(self) -> None:
        assert ReviewResponseParser()._parse_md_suggestion_line("plain text") is None

    def test_parse_md_suggestion_line_when_empty_then_none(self) -> None:
        assert ReviewResponseParser()._parse_md_suggestion_line("-  ") is None

    def test_parse_md_praise_line_when_file_then_fields(self) -> None:
        entry = ReviewResponseParser()._parse_md_praise_line("- src/a.py: solid design")

        assert entry == {"file": "src/a.py", "description": "solid design"}

    def test_parse_md_praise_line_when_plain_then_text(self) -> None:
        entry = ReviewResponseParser()._parse_md_praise_line("- nice naming")

        assert entry == {"file": "", "description": "nice naming"}

    def test_parse_md_praise_line_when_none_then_none(self) -> None:
        assert ReviewResponseParser()._parse_md_praise_line("- none") is None

    def test_parse_md_praise_line_when_unparsable_then_none(self) -> None:
        assert ReviewResponseParser()._parse_md_praise_line("not a bullet") is None

    def test_extract_suggestions_md_when_section_then_entries(self) -> None:
        content = "## Suggestions\n- src/a.py: Reuse helper\n- Second thought\n"

        result = ReviewResponseParser()._extract_suggestions_md(content)

        assert len(result) == 2

    def test_extract_suggestions_md_when_absent_then_empty(self) -> None:
        assert ReviewResponseParser()._extract_suggestions_md("none") == []

    def test_extract_praise_md_when_section_then_entries(self) -> None:
        content = "## Praise\n- Great coverage\n- Clean code\n"

        result = ReviewResponseParser()._extract_praise_md(content)

        assert len(result) == 2

    def test_extract_praise_md_when_absent_then_empty(self) -> None:
        assert ReviewResponseParser()._extract_praise_md("none") == []

    def test_strip_frontmatter_when_present_then_removed(self) -> None:
        text = "---\nmodel: x\n---\n## Verdict\napproved"

        assert ReviewResponseParser.strip_frontmatter(text) == "## Verdict\napproved"

    def test_strip_frontmatter_when_absent_then_unchanged(self) -> None:
        assert ReviewResponseParser.strip_frontmatter("plain") == "plain"

    def test_strip_frontmatter_when_single_delimiter_then_stripped_text(self) -> None:
        assert ReviewResponseParser.strip_frontmatter("---\nmodel: x\n") == "---\nmodel: x"

