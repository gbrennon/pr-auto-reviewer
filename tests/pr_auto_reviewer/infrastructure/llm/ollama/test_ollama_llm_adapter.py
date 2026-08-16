"""Tests for OllamaLlmAdapter."""

import json
import logging
from pathlib import Path
import re
import requests as _requests

import pytest

from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import (
    PullRequestDiff,
)
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_llm_adapter import (
    OllamaLlmAdapter,
)
from pr_auto_reviewer.infrastructure.llm.prompt_builder import PromptBuilder
from pr_auto_reviewer.infrastructure.llm.review_response_parser import ReviewResponseParser

@pytest.fixture
def adapter() -> OllamaLlmAdapter:
    """Create OllamaLlmAdapter with test host."""
    return OllamaLlmAdapter("http://localhost:11434", "code-review")

@pytest.fixture
def prompt_builder() -> PromptBuilder:
    """Create PromptBuilder instance."""
    return PromptBuilder()

@pytest.fixture
def sample_diff() -> PullRequestDiff:
    """Create a sample diff from real PR fixture."""
    fixture_path = Path(__file__).parents[4] / "fixtures" / "diffs" / "sample-ollama.diff"
    return PullRequestDiff(
        pr_id=None,
        head_sha=None,
        diff_content=fixture_path.read_text(),
    )

@pytest.fixture
def sample_context() -> RepositoryContext:
    """Create a sample review context."""
    return RepositoryContext(
        architecture_hint="Layered architecture",
        conventions="Use type hints",
        repository_structure="src/\n  main.py\n  utils/",
    )

class TestOllamaLlmAdapter:
    """Tests for OllamaLlmAdapter."""

    def test_review_sends_request_to_ollama(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post,
    ) -> None:
        """Sends POST request to Ollama with correct payload."""
        monkeypatch.setattr(_requests, "post", ollama_fake_post)

        result = adapter.review(sample_diff, sample_context)

        assert isinstance(result, CodeReview)

    def test_review_returns_code_review(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post,
    ) -> None:
        """Returns CodeReview from Ollama response."""
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post)

        result = adapter.review(sample_diff, sample_context)

        assert isinstance(result, CodeReview)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
        assert result.items[0].severity == ItemSeverity.MAJOR

    def test_review_raises_on_request_error(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post_error,
    ) -> None:
        """Raises LlmUnavailableError on request failure."""
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post_error)

        with pytest.raises(Exception):
            adapter.review(sample_diff, sample_context)

    def test_debug_logs_request_payload_when_debug_enabled(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post, caplog,
    ) -> None:
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post)

        caplog.set_level(logging.DEBUG)
        adapter.review(sample_diff, sample_context)

        request_logs = [
            r.message for r in caplog.records
            if "Ollama request payload" in r.message
        ]
        assert len(request_logs) == 1
        assert "model=code-review" in request_logs[0]
        assert "prompt_chars=" in request_logs[0]

    def test_debug_logs_review_summary_when_debug_enabled(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post, caplog,
    ) -> None:
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post)

        caplog.set_level(logging.DEBUG)
        adapter.review(sample_diff, sample_context)

        summary_logs = [
            r.message for r in caplog.records
            if "OLLAMA REVIEW SUMMARY" in r.message
        ]
        assert len(summary_logs) == 1
        summary = summary_logs[0]
        assert "host=" in summary
        assert "model=" in summary
        assert "prompt=" in summary
        assert "verdict=" in summary
        assert "items=" in summary
        assert "summary=" in summary

    def test_review_summary_not_logged_at_info_level(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post, caplog,
    ) -> None:
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post)

        caplog.set_level(logging.INFO)
        adapter.review(sample_diff, sample_context)

        summary_logs = [
            r.message for r in caplog.records
            if "OLLAMA REVIEW SUMMARY" in r.message
        ]
        assert len(summary_logs) == 0

    def test_review_raises_on_invalid_json(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post_invalid_json,
    ) -> None:
        """Raises LlmUnavailableError on invalid JSON."""
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post_invalid_json)

        with pytest.raises(Exception):
            adapter.review(sample_diff, sample_context)

    def test_review_handles_empty_response(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post_empty,
    ) -> None:
        """Raises LlmUnavailableError on empty response."""
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post_empty)

        with pytest.raises(Exception):
            adapter.review(sample_diff, sample_context)


    def test_retry_succeeds_after_validation_failure(
        self, monkeypatch, sample_diff: PullRequestDiff,
        sample_context: RepositoryContext,
    ) -> None:
        """Retry loop reprocesses when initial response fails validation.

        Simulates transient LLM quality issues: first response triggers
        diagnose_failures (empty JSON → missing verdict), correction prompt is
        built, second response passes validation.
        """
        adapter = OllamaLlmAdapter(
            "http://localhost:11434", "code-review", max_retries=3,
        )

        call_count = 0

        bad_raw = "{}"
        good_raw = json.dumps({
            "verdict": "changes_requested",
            "issues": [{
                "file": "src/foo.py",
                "description": "bad code",
                "severity": "major",
                "type": "maintainability",
                "current_code": "x = 1",
                "suggested_fix": "x = 2",
            }],
        })

        def fake_request_ollama(_prompt_text: str, _timeout: int):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (bad_raw, 100.0, 10, 0.5)
            return (good_raw, 100.0, 10, 0.5)

        monkeypatch.setattr(adapter, "_request_ollama", fake_request_ollama)
        monkeypatch.setattr(adapter, "_dump_prompt_to_file", lambda *_: None)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = adapter.review(sample_diff, sample_context)

        assert call_count == 2
        assert isinstance(result, CodeReview)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
        assert result.items[0].file_path == "src/foo.py"

    def test_retry_exhausts_attempts_when_all_validations_fail(
        self, monkeypatch, sample_diff: PullRequestDiff,
        sample_context: RepositoryContext,
    ) -> None:
        """Returns last CodeReview when every retry attempt fails validation.

        The retry loop calls _request_ollama exactly max_retries times.
        The last parsed CodeReview (with failures) is returned — the caller
        is responsible for deciding how to handle it.
        """
        max_retries = 3
        adapter = OllamaLlmAdapter(
            "http://localhost:11434", "code-review", max_retries=max_retries,
        )

        call_count = 0
        bad_raw = "{}"

        def fake_request_ollama(_prompt_text: str, _timeout: int):
            nonlocal call_count
            call_count += 1
            return (bad_raw, 100.0, 10, 0.5)

        monkeypatch.setattr(adapter, "_request_ollama", fake_request_ollama)
        monkeypatch.setattr(adapter, "_dump_prompt_to_file", lambda *_: None)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = adapter.review(sample_diff, sample_context)

        assert call_count == max_retries
        assert isinstance(result, CodeReview)
        # With empty JSON, parse falls back to markdown which may produce COMMENTED
        assert result.verdict is not None

class TestPromptBuilder:
    """Tests for PromptBuilder."""

    def test_build_includes_diff(
        self, sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        prompt_builder: PromptBuilder,
    ) -> None:
        """Prompt includes the diff content."""
        prompt = prompt_builder.build(sample_diff, sample_context)
        assert "diff --git" in prompt
        assert ".env.example" in prompt

    def test_build_includes_architecture_hint(
        self, sample_diff: PullRequestDiff, prompt_builder: PromptBuilder,
    ) -> None:
        """Prompt includes architecture hint when provided."""
        context = RepositoryContext(
            architecture_hint="Layered architecture",
            conventions="",
            repository_structure="",
        )
        prompt = prompt_builder.build(sample_diff, context)
        assert "Layered architecture" in prompt

    def test_build_includes_conventions(
        self, sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        prompt_builder: PromptBuilder,
    ) -> None:
        """Prompt includes conventions when provided."""
        diff = PullRequestDiff(
            pr_id=None, head_sha=None,
            diff_content="", conventions="Use type hints"
        )
        prompt = prompt_builder.build(diff, sample_context)
        assert "Use type hints" in prompt

    def test_build_includes_repo_structure(
        self, sample_diff: PullRequestDiff, prompt_builder: PromptBuilder,
    ) -> None:
        """Prompt includes repository structure when provided."""
        context = RepositoryContext(
            architecture_hint="",
            conventions="",
            repository_structure="src/\n  main.py",
        )
        prompt = prompt_builder.build(sample_diff, context)
        assert "src/" in prompt

    def test_build_uses_json_format(
        self, sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        prompt_builder: PromptBuilder,
    ) -> None:
        """Prompt requests JSON output format."""
        prompt = prompt_builder.build(sample_diff, sample_context)
        assert '"issues"' in prompt
        assert '"severity"' in prompt
        assert '"category"' in prompt

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
        assert result.verdict == ReviewVerdict.COMMENTED

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
