"""Tests for OllamaExploratoryChatAdapter."""

from __future__ import annotations
from pathlib import Path

import json
import time as _time
from typing import Any

import pytest
import requests as _requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter import (
    OllamaExploratoryChatAdapter,
)


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


@pytest.fixture
def adapter() -> OllamaExploratoryChatAdapter:
    """Create OllamaExploratoryChatAdapter with low retries for fast tests."""
    return OllamaExploratoryChatAdapter(model="phi4", max_retries=2, ollama_timeout=10)


@pytest.fixture
def prompt_no_repo() -> ComposedPrompt:
    """ComposedPrompt without repo_path — triggers single-pass path."""
    return ComposedPrompt(
        content="Review this diff:\n```diff\n+ x = 1\n```",
        fragments_used=["frag-1"],
        total_tokens=50,
    )


@pytest.fixture
def prompt_with_repo(tmp_path: Path) -> ComposedPrompt:
    """ComposedPrompt with repo_path — triggers multi-turn path."""
    return ComposedPrompt(
        content="System prompt for exploratory review",
        fragments_used=["system-prompt"],
        total_tokens=500,
        repo_path=str(tmp_path),
    )


class TestSinglePass:
    """Tests for _single_pass (empty repo_path)."""

    def test_returns_code_review(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_no_repo: ComposedPrompt,
    ) -> None:
        """Streaming chat response is parsed into a CodeReview."""
        verdict_json = _make_verdict_json()

        def fake_post(
            url: str,
            *,
            json: dict[str, Any] | None = None,
            timeout: int | None = None,
            stream: bool = False,
            **kwargs: object,
        ) -> _FakeStreamingResponse:
            assert "/api/chat" in url
            assert json is not None
            assert json["stream"] is True
            assert json["format"] == "json"
            assert json["messages"][0]["role"] == "user"
            assert json["messages"][0]["content"] == prompt_no_repo.content
            return _FakeStreamingResponse(verdict_json)

        monkeypatch.setattr(_requests, "post", fake_post)

        result = adapter.review_prompt(prompt_no_repo)

        assert isinstance(result, CodeReview)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
        assert result.items[0].severity == ItemSeverity.MAJOR
        assert result.items[0].file_path == "src/foo.py"

    def test_raises_on_empty_response(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_no_repo: ComposedPrompt,
    ) -> None:
        """Raises LlmUnavailableError when streaming returns empty content."""
        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse("")

        monkeypatch.setattr(_requests, "post", fake_post)

        with pytest.raises(LlmUnavailableError, match="Empty response"):
            adapter.review_prompt(prompt_no_repo)

    def test_raises_on_request_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_no_repo: ComposedPrompt,
    ) -> None:
        """Raises LlmUnavailableError when POST fails."""
        def fake_post(*args: object, **kwargs: object) -> None:
            raise _requests.RequestException("Connection refused")

        monkeypatch.setattr(_requests, "post", fake_post)

        with pytest.raises(LlmUnavailableError, match="failed after 2 attempts"):
            adapter.review_prompt(prompt_no_repo)

    def test_retry_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_no_repo: ComposedPrompt,
    ) -> None:
        """Retries on first failure then returns CodeReview on second attempt."""
        verdict_json = _make_verdict_json(verdict="APPROVED", issues=[])
        call_count = 0

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _requests.RequestException("Temporary failure")
            return _FakeStreamingResponse(verdict_json)

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(_time, "sleep", lambda _: None)

        result = adapter.review_prompt(prompt_no_repo)
        assert call_count == 2
        assert result.verdict == ReviewVerdict.APPROVED

    def test_retry_exhaustion(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_no_repo: ComposedPrompt,
    ) -> None:
        """Raises LlmUnavailableError after all retries exhausted."""
        call_count = 0

        def fake_post(*args: object, **kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            raise _requests.RequestException("Fatal error")

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(_time, "sleep", lambda _: None)

        with pytest.raises(LlmUnavailableError, match="failed after 2 attempts"):
            adapter.review_prompt(prompt_no_repo)
        assert call_count == 2




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

        assert len(calls) == 2
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1

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

        assert len(calls) == 3
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

        assert len(calls) == 2
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

        with pytest.raises(LlmUnavailableError, match="Exceeded max turns"):
            adapter.review_prompt(prompt_with_repo)

    def test_streaming_accumulates_chunks(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_no_repo: ComposedPrompt,
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

        result = adapter.review_prompt(prompt_no_repo)

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

        assert len(calls) == 2
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED