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
