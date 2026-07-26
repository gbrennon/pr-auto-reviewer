"""Tests for OllamaExploratoryChatAdapter."""

from __future__ import annotations
from pathlib import Path

import json
import time as _time
import tempfile
from typing import Any

import pytest
import requests as _requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter import (
    OllamaExploratoryChatAdapter,
)


class _FakeStreamingResponse:
    """Minimal fake requests.Response with streaming iter_lines."""

    def __init__(self, content: str, *, status_code: int = 200) -> None:
        self._content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        pass

    def iter_lines(self, decode_unicode: bool) -> list[str]:
        """Simulate NDJSON chunks — one chunk for content, then a done marker."""
        return [
            json.dumps({"message": {"content": self._content}, "done": False}),
            json.dumps({"message": {"content": ""}, "done": True}),
        ]



def _make_verdict_json(
    verdict: str = "CHANGES_REQUESTED",
    issues: list[dict[str, Any]] | None = None,
) -> str:
    """Build a minimal verdict JSON response string."""
    if issues is None:
        issues = [
            {
                "file": "src/foo.py",
                "line": "42",
                "severity": "major",
                "category": "security",
                "description": "SQL injection risk",
                "current_code": "query = 'SELECT * FROM users WHERE id = ' + uid",
                "suggested_fix": "query = 'SELECT * FROM users WHERE id = %s'",
            }
        ]
    return json.dumps(
        {
            "verdict": verdict,
            "summary": "Found issues in review",
            "issues": issues,
            "suggestions": [],
            "praise": [],
        }
    )


def _make_action_json(action: str, args: str) -> str:
    """Build a JSON tool-call response string."""
    return json.dumps({"action": action, "args": args})


@pytest.fixture
def adapter() -> OllamaExploratoryChatAdapter:
    """Create OllamaExploratoryChatAdapter with low retries for fast tests."""
    return OllamaExploratoryChatAdapter(model="phi4", max_retries=2, ollama_timeout=10)



@pytest.fixture
def prompt_with_repo(tmp_path: Path) -> ComposedPrompt:
    """ComposedPrompt with repo_path — triggers multi-turn path."""
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "foo.py").write_text("def foo() -> None: ...")
    (tmp_path / "src" / "a.py").write_text("def a() -> None: ...")
    return ComposedPrompt(
        content="System prompt for exploratory review",
        fragments_used=["system-prompt"],
        total_tokens=500,
        repo_path=str(tmp_path),
    )



class TestMultiTurn:
    """Tests for _multi_turn (non-empty repo_path)."""

    def test_single_tool_then_verdict(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Models calls one tool then emits verdict."""
        calls: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            json: dict[str, Any] | None = None,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            calls.append(dict(json or {}))
            call_idx = len(calls)
            if call_idx == 1:
                return _FakeStreamingResponse(_make_action_json("read_file", "src/foo.py"))
            return _FakeStreamingResponse(_make_verdict_json())

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: f"File contents of {args}",
        )

        result = adapter.review_prompt(prompt_with_repo)

        assert len(calls) == 4
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1


    def test_handles_list_format_args(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Model sends args as JSON array — adapter joins to space-separated string."""
        captured_args: list[str] = []
        calls: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            json_data: dict[str, Any] = kwargs.get("json", {})
            calls.append(dict(json_data))
            call_idx = len(calls)
            if call_idx == 1:
                return _FakeStreamingResponse(
                    json.dumps({"action": "run_git", "args": ["diff", "--name-only"]})
                )
            return _FakeStreamingResponse(_make_verdict_json())

        def fake_execute(self: object, action: str, args: str) -> str:
            captured_args.append(args)
            return f"Result for {action} {args}"

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            fake_execute,
        )

        result = adapter.review_prompt(prompt_with_repo)

        assert len(captured_args) == 1
        assert captured_args[0] == "diff --name-only"
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_verdict_with_empty_items_valid(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Model emits verdict with no findings — valid response, not unparseable."""
        calls: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            json_data: dict[str, Any] = kwargs.get("json", {})
            calls.append(dict(json_data))
            return _FakeStreamingResponse(
                json.dumps({"verdict": "approved", "items": []})
            )
        monkeypatch.setattr(_requests, "post", fake_post)

        result = adapter.review_prompt(prompt_with_repo)

        assert result.verdict == ReviewVerdict.APPROVED
        assert len(result.items) == 0

    def test_two_tools_then_verdict(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Model calls two tools sequentially before verdict."""
        calls: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            json: dict[str, Any] | None = None,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            calls.append(dict(json or {}))
            call_idx = len(calls)
            if call_idx == 1:
                return _FakeStreamingResponse(_make_action_json("read_file", "src/a.py"))
            if call_idx == 2:
                return _FakeStreamingResponse(_make_action_json("search_codebase", "bad_func"))
            return _FakeStreamingResponse(_make_verdict_json())

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: f"Result for {action} {args}",
        )

        result = adapter.review_prompt(prompt_with_repo)

        assert len(calls) == 5
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_handles_non_json_response(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Non-JSON model output is appended and conversation continues."""
        calls: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            json: dict[str, Any] | None = None,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            calls.append(dict(json or {}))
            call_idx = len(calls)
            if call_idx == 1:
                return _FakeStreamingResponse("I will now explore the codebase.")
            return _FakeStreamingResponse(_make_verdict_json())

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "OK",
        )

        result = adapter.review_prompt(prompt_with_repo)

        assert len(calls) == 4
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_raises_on_max_turns_exceeded(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Raises LlmUnavailableError after _MAX_TURNS without a verdict."""
        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                _make_action_json("list_directory", ".")
            )

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "file1.py\nfile2.py",
        )

        with pytest.raises(LlmUnavailableError, match="Phase exceeded max turns"):
            adapter.review_prompt(prompt_with_repo)

    def test_streaming_accumulates_chunks(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Multiple streaming chunks are accumulated before parsing."""

        class _MultiChunkResponse:
            status_code = 200

            def raise_for_status(self) -> None:
                pass

            def iter_lines(self, decode_unicode: bool) -> list[str]:
                verdict = _make_verdict_json()
                mid = len(verdict) // 2
                return [
                    json.dumps({"message": {"content": verdict[:mid]}, "done": False}),
                    json.dumps({"message": {"content": verdict[mid:]}, "done": True}),
                ]

        monkeypatch.setattr(_requests, "post", lambda *a, **kw: _MultiChunkResponse())

        result = adapter.review_prompt(prompt_with_repo)

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1


    def test_ignores_json_without_action_or_verdict(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Valid JSON without action or verdict keys is appended and ignored."""
        calls: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            json_data: dict[str, Any] | None = None,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            calls.append(dict(json_data or {}))
            call_idx = len(calls)
            if call_idx == 1:
                return _FakeStreamingResponse(
                    json.dumps({"thinking": "analyzing..."})
                )
            return _FakeStreamingResponse(_make_verdict_json())

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "OK",
        )

        result = adapter.review_prompt(prompt_with_repo)

        assert len(calls) == 4
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_empty_response_recovers_on_next_turn(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Single empty response triggers reprompt; next turn succeeds."""
        calls: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            json: dict[str, Any] | None = None,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            calls.append(dict(json or {}))
            call_idx = len(calls)
            if call_idx == 1:
                return _FakeStreamingResponse("")
            return _FakeStreamingResponse(_make_verdict_json())

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "OK",
        )

        result = adapter.review_prompt(prompt_with_repo)

        assert len(calls) == 4
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1

    def test_empty_response_exhaustion_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Three consecutive empty responses raise LlmUnavailableError."""
        calls: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            json: dict[str, Any] | None = None,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            calls.append(dict(json or {}))
            return _FakeStreamingResponse("")

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "OK",
        )

        with pytest.raises(
            LlmUnavailableError, match="empty response 3 consecutive"
        ):
            adapter.review_prompt(prompt_with_repo)

        assert len(calls) == 3

    def test_empty_response_counter_resets_after_valid(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Non-consecutive empties reset counter; doesn't raise."""
        calls: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            json: dict[str, Any] | None = None,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            calls.append(dict(json or {}))
            call_idx = len(calls)
            if call_idx in (1, 3):
                return _FakeStreamingResponse("")
            return _FakeStreamingResponse(_make_verdict_json())

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "OK",
        )

        result = adapter.review_prompt(prompt_with_repo)

        assert len(calls) == 5
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1

    def test_unparseable_response_recovers_on_next_turn(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Two unparseable responses trigger reprompt; next turn succeeds."""
        calls: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            json: dict[str, Any] | None = None,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            calls.append(dict(json or {}))
            call_idx = len(calls)
            if call_idx <= 2:
                return _FakeStreamingResponse("not valid json {{{")
            return _FakeStreamingResponse(_make_verdict_json())

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "OK",
        )

        result = adapter.review_prompt(prompt_with_repo)

        assert len(calls) == 5
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1

    def test_unparseable_response_exhaustion_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Three consecutive unparseable responses raise LlmUnavailableError."""
        calls: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            json: dict[str, Any] | None = None,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            calls.append(dict(json or {}))
            return _FakeStreamingResponse("<html>not json</html>")

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "OK",
        )

        with pytest.raises(
            LlmUnavailableError, match="unparseable response 3 consecutive"
        ):
            adapter.review_prompt(prompt_with_repo)

        assert len(calls) == 3

    def test_unparseable_response_counter_resets_after_valid(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Non-consecutive unparseable resets counter; doesn't raise."""
        calls: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            json: dict[str, Any] | None = None,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            calls.append(dict(json or {}))
            call_idx = len(calls)
            if call_idx == 1:
                return _FakeStreamingResponse("bad json {{{")
            if call_idx == 3:
                return _FakeStreamingResponse("<html>oops</html>")
            return _FakeStreamingResponse(_make_verdict_json())

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "OK",
        )

        result = adapter.review_prompt(prompt_with_repo)

        assert len(calls) == 5
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1

    def test_raises_on_request_error(
        self,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
        monkeypatch: Any,
    ) -> None:
        call_count = 0

        def fake_post(*args: object, **kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            raise _requests.RequestException("Connection refused")

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(_time, "sleep", lambda s: None)

        with pytest.raises(LlmUnavailableError, match="failed after 2 attempts"):
            adapter.review_prompt(prompt_with_repo)

        assert call_count == 2

    def test_thinking_fallback_when_content_empty(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """When content chunks are all empty, fall back to thinking chunks."""

        class _ThinkingOnlyResponse:
            status_code = 200

            def raise_for_status(self) -> None:
                pass

            def iter_lines(self, decode_unicode: bool) -> list[str]:
                verdict = _make_verdict_json()
                mid = len(verdict) // 2
                return [
                    json.dumps({"message": {"thinking": verdict[:mid]}, "done": False}),
                    json.dumps({"message": {"thinking": verdict[mid:]}, "done": False}),
                    json.dumps({"message": {}, "done": True}),
                ]

        monkeypatch.setattr(_requests, "post", lambda *a, **kw: _ThinkingOnlyResponse())

        result = adapter.review_prompt(prompt_with_repo)

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
    def test_payload_does_not_include_format_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """The _stream_chat payload does NOT include 'format' — natural language allowed."""
        payloads: list[dict[str, Any]] = []

        def fake_post(
            url: str,
            *,
            json: dict[str, Any] | None = None,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            if json is not None:
                payloads.append(json)
            return _FakeStreamingResponse(_make_verdict_json())

        monkeypatch.setattr(_requests, "post", fake_post)

        adapter.review_prompt(prompt_with_repo)

        assert len(payloads) >= 1
        assert "format" not in payloads[0]

    def test_dumps_conversation_on_exhaustion(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
        tmp_path: Path,
    ) -> None:
        """Max-turns exhaustion dumps conversation to a temp file."""

        _real_mkstemp = tempfile.mkstemp
        written_paths: list[str] = []

        def fake_mkstemp(prefix: str, suffix: str) -> tuple[int, str]:
            fd, path = _real_mkstemp(prefix=prefix, suffix=suffix, dir=str(tmp_path))
            written_paths.append(path)
            return (fd, path)


        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                _make_action_json("list_directory", ".")
            )

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "file1.py\nfile2.py",
        )
        monkeypatch.setattr(tempfile, "mkstemp", fake_mkstemp)

        with pytest.raises(LlmUnavailableError, match="Phase exceeded max turns"):
            adapter.review_prompt(prompt_with_repo)

        assert len(written_paths) == 1
        dumped = json.loads(Path(written_paths[0]).read_text())
        assert isinstance(dumped, list)
        assert any("list_directory" in json.dumps(m) for m in dumped)
        Path(written_paths[0]).unlink()


class TestExtractFileListing:
    """Tests for _extract_file_listing static method."""

    def test_extracts_files_from_diff_section(self) -> None:
        """Parses --- a/path and +++ b/path lines after ## Diff header."""
        content = "some text\n## Diff\n--- a/src/foo.py\n+++ b/src/foo.py\nmore\n--- a/lib/bar.py\n+++ b/lib/bar.py\n"
        result = OllamaExploratoryChatAdapter._extract_file_listing(content)
        assert result == ["lib/bar.py", "src/foo.py"]
    def test_skips_dev_null(self) -> None:
        """Lines with /dev/null are excluded; other paths in the same diff are kept."""
        content = "## Diff\n--- /dev/null\n+++ b/src/new.py\n--- a/src/old.py\n+++ /dev/null\n--- a/src/keep.py\n+++ b/src/keep.py\n"
        result = OllamaExploratoryChatAdapter._extract_file_listing(content)
        assert "src/keep.py" in result
        assert "src/new.py" in result
        assert "src/old.py" in result
        assert all("/dev/null" not in p for p in result)

    def test_handles_no_diff_section(self) -> None:
        """Returns empty list when no ## Diff header present."""
        result = OllamaExploratoryChatAdapter._extract_file_listing("just some text\nno headers\n")
        assert result == []

    def test_deduplicates_paths(self) -> None:
        """Same file appearing multiple times yields one entry."""
        content = "## Diff\n--- a/src/foo.py\n+++ b/src/foo.py\n--- a/src/foo.py\n+++ b/src/foo.py\n"
        result = OllamaExploratoryChatAdapter._extract_file_listing(content)
        assert result == ["src/foo.py"]


class TestBuildReviewItemsValidation:
    """Tests for _build_review_items path validation."""

    def test_real_paths_are_accepted(self, tmp_path: Path) -> None:
        """Items with existing file paths are kept."""
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "real.py").write_text("pass")
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {"file": "src/real.py", "severity": "major", "category": "bug", "description": "bad", "line": "1", "current_code": "pass", "suggested_fix": "return None"}
        ]
        result = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].file_path == "src/real.py"

    def test_hallucinated_paths_are_skipped(self, tmp_path: Path) -> None:
        """Items referencing non-existent files are dropped with warning."""
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {"file": "nonexistent.py", "severity": "critical", "category": "security", "description": "fake", "line": "", "current_code": "", "suggested_fix": ""}
        ]
        result = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 0

    def test_mixed_real_and_hallucinated(self, tmp_path: Path) -> None:
        """Only valid items survive; numbering is sequential."""
        (tmp_path / "valid.py").write_text("ok")
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {"file": "valid.py", "severity": "minor", "category": "style", "description": "ok", "line": "", "current_code": "ok", "suggested_fix": ""},
            {"file": "fake.py", "severity": "critical", "category": "security", "description": "invented", "line": "", "current_code": "", "suggested_fix": ""},
            {"file": "valid.py", "severity": "major", "category": "bug", "description": "also ok", "line": "", "current_code": "also ok", "suggested_fix": ""},
        ]
        result = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 2
        assert result[0].number == 1
        assert result[1].number == 2

    def test_strips_ab_prefix(self, tmp_path: Path) -> None:
        """File paths with a/ or b/ prefix are normalized before validation."""
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        (tmp_path / "src" / "lib.py").write_text("pass")
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {"file": "a/src/lib.py", "severity": "info", "category": "maintainability", "description": "nice", "line": "", "current_code": "pass", "suggested_fix": ""},
        ]
        result = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].file_path == "src/lib.py"

    def test_empty_file_path_passes_validation(self, tmp_path: Path) -> None:
        """Items with empty file_path are not validated (cross-cutting findings)."""
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {"file": "", "severity": "major", "category": "architecture", "description": "global concern", "line": "", "current_code": "", "suggested_fix": ""},
        ]
        result = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 1

    def test_nonempty_file_path_with_empty_code_is_skipped(
        self, tmp_path: Path
    ) -> None:
        """Items with a real file path but no code evidence are dropped."""
        adapter = OllamaExploratoryChatAdapter(
            model="test", max_retries=1, ollama_timeout=1
        )
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "empty.py").write_text("")
        item_dicts: list[dict[str, Any]] = [
            {
                "file": "src/empty.py",
                "severity": "major",
                "category": "bug",
                "description": "hallucinated finding",
                "line": "",
                "current_code": "",
                "suggested_fix": "",
            },
            {
                "file": "",
                "severity": "info",
                "category": "architecture",
                "description": "cross-cutting is fine",
                "line": "",
                "current_code": "",
                "suggested_fix": "",
            },
        ]
        result = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].description == "cross-cutting is fine"
