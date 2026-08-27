from ._helpers import *


class TestReviewResponseParser:
    """Tests for ReviewResponseParser."""

    def test_parse_json_returns_code_review(self) -> None:
        """Parses JSON response correctly."""
        raw_text = json.dumps({
            "issues": [
                {"file": "foo.py", "line": "3", "severity": "high",
                 "type": "security", "description": "test issue",
                 "current_code": "+ password = request.args['password']",
                 "suggested_fix": "password = request.form['password']"}
            ],
            "summary": "Test summary",
            "suggestions": [],
            "praise": []
        })
        result = ReviewResponseParser().parse(raw_text, "code-review")

        assert isinstance(result, CodeReview)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
        assert result.items[0].severity == ItemSeverity.MAJOR
        assert result.items[0].category == "security"

    def test_parse_json_changes_requested_for_items_without_verdict(
        self,
    ) -> None:
        """Returns CHANGES_REQUESTED when items exist but no explicit verdict."""
        raw_text = json.dumps({
            "issues": [
                {"file": "foo.py", "line": "3", "severity": "low",
                 "type": "quality", "description": "minor issue",
                 "current_code": "+ x = 1",
                 "suggested_fix": "x = DEFAULT_VALUE"}
            ],
            "summary": "Looks good",
            "suggestions": [],
            "praise": []
        })
        result = ReviewResponseParser().parse(raw_text, "code-review")

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_parse_json_fallback_to_markdown(
        self,
    ) -> None:
        """Falls back to markdown parsing when JSON fails."""
        raw_text = """## Verdict
approved

Looks good

None
"""
        result = ReviewResponseParser().parse(raw_text, "code-review")

        assert result.verdict == ReviewVerdict.APPROVED
        assert "Looks good" in result.summary

    def test_parse_json_extracts_items(self) -> None:
        """Extracts items from JSON response."""
        raw_text = json.dumps({
            "issues": [
                {"file": "foo.py", "line": "3", "severity": "critical",
                 "type": "security", "description": "buffer overflow",
                 "current_code": "+ strcpy(dst, src)",
                 "suggested_fix": "strncpy(dst, src, sizeof(dst) - 1)"},
                {"file": "bar.py", "line": "10", "severity": "major",
                 "type": "architecture", "description": "god object",
                 "current_code": "+ class GodObject:",
                 "suggested_fix": "class FocusedService:"}
            ],
            "summary": "Has issues",
            "suggestions": [],
            "praise": []
        })
        result = ReviewResponseParser().parse(raw_text, "code-review")

        assert len(result.items) == 2
        assert result.items[0].severity == ItemSeverity.CRITICAL
        assert result.items[1].severity == ItemSeverity.MAJOR

    def test_parse_json_handles_empty_issues(self) -> None:
        """Handles empty issues array."""
        raw_text = json.dumps({
            "issues": [],
            "summary": "Looks good",
            "suggestions": [],
            "praise": []
        })
        result = ReviewResponseParser().parse(raw_text, "code-review")

        assert len(result.items) == 0
        assert result.verdict == ReviewVerdict.APPROVED

    @pytest.mark.parametrize("severity,expected_verdict", [
        ("critical", ReviewVerdict.CHANGES_REQUESTED),
        ("high", ReviewVerdict.CHANGES_REQUESTED),
        ("medium", ReviewVerdict.CHANGES_REQUESTED),
        ("low", ReviewVerdict.CHANGES_REQUESTED),
        ("info", ReviewVerdict.CHANGES_REQUESTED),
    ])
    def test_parse_markdown_code_block_verdict(
        self, severity: str, expected_verdict: ReviewVerdict,
    ) -> None:
        """Verdict is determined correctly from severity in markdown code blocks."""
        raw_text = f'''```json
{{
  "issues": [
    {{"file": "foo.py", "line": "10", "severity": "{severity}",
     "type": "security", "description": "test issue",
     "current_code": "+ password = request.args['password']",
     "suggested_fix": "password = request.form['password']"}}
  ],
  "summary": "Test summary",
  "suggestions": [],
  "praise": []
}}
```'''
        result = ReviewResponseParser().parse(raw_text, "code-review")

        assert result.verdict == expected_verdict
        assert len(result.items) == 1

    def test_parse_markdown_code_block_with_empty_lang(self) -> None:
        """Parses JSON from code blocks without json language specifier."""
        raw_text = '''```
{
  "issues": [
    {"file": "foo.py", "line": "10", "severity": "high",
     "type": "security", "description": "critical issue",
     "current_code": "+ password = request.args['password']",
     "suggested_fix": "password = request.form['password']"}
  ],
  "summary": "Fix required",
  "suggestions": [],
  "praise": []
}
```'''
        result = ReviewResponseParser().parse(raw_text, "code-review")

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
        assert "critical issue" in result.items[0].description

    def test_parse_markdown_code_block_with_multiple_issues(self) -> None:
        """Correctly parses multiple issues from markdown code blocks."""
        raw_text = '''```json
{
  "issues": [
    {"file": "auth.rs", "line": "42", "severity": "high",
     "type": "security", "description": "SQL injection risk",
     "current_code": "+ query(user_input);",
     "suggested_fix": "query_with_params(user_input);"},
    {"file": "utils.rs", "line": "15", "severity": "low",
     "type": "quality", "description": "unused import",
     "current_code": "+ use crate::unused;",
     "suggested_fix": "use crate::used;"}
  ],
  "summary": "One critical issue found",
  "suggestions": [],
  "praise": []
}
```'''
        result = ReviewResponseParser().parse(raw_text, "code-review")

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 2
        assert result.items[0].file_path == "auth.rs"
        assert result.items[1].file_path == "utils.rs"

    def test_parse_plain_json_still_works(self) -> None:
        """Plain JSON (no code block) is still parsed correctly."""
        raw_text = json.dumps({
            "issues": [
                {"file": "main.py", "line": "5", "severity": "high",
                 "type": "architecture", "description": "needs refactor",
                 "current_code": "+ class GodObject:",
                 "suggested_fix": "class FocusedService:"}
            ],
            "summary": "Needs changes",
            "suggestions": [],
            "praise": []
        })
        result = ReviewResponseParser().parse(raw_text, "code-review")

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
        assert result.summary == "Needs changes"

    def test_parse_markdown_fallback_still_works(self) -> None:
        """Markdown format still falls back correctly."""
        raw_text = """## Verdict
changes_requested

Code needs work

- [critical] security (auth.py): vulnerability found
"""
        result = ReviewResponseParser().parse(raw_text, "code-review")

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert "Code needs work" in result.summary

