"""Tests for OllamaExploratoryChatAdapter multi-turn functionality."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
import requests as _requests

from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_exploratory_chat_adapter import (
    OllamaExploratoryChatAdapter,
)
from tests.pr_auto_reviewer.infrastructure.llm._test_helpers import (
    TestHelpers,
    _FakeStreamingResponse,
)


class TestMultiTurn:
    """Tests for _multi_turn (non-empty repo_path)."""

    def test_single_tool_then_verdict(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Single tool call followed by verdict."""
        calls: list[int] = []

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            calls.append(1)
            if len(calls) == 1:
                return _FakeStreamingResponse(
                    TestHelpers.make_action_json("list_directory", ".")
                )
            return _FakeStreamingResponse(
                TestHelpers.make_verdict_json("APPROVED", issues=[])
            )

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "file1.py\nfile2.py",
        )

        result = adapter.review_prompt(prompt_with_repo)
        assert result.verdict == ReviewVerdict.APPROVED
        assert len(result.items) == 0

    def test_multiple_tools_then_verdict(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Multiple tool calls followed by verdict."""
        calls: list[int] = []

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            calls.append(1)
            if len(calls) == 1:
                return _FakeStreamingResponse(
                    TestHelpers.make_action_json("read_file", "src/foo.py")
                )
            return _FakeStreamingResponse(
                TestHelpers.make_verdict_json("CHANGES_REQUESTED")
            )

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "file1.py\nfile2.py",
        )

        repo_path = Path(prompt_with_repo.repo_path)
        (repo_path / "src" / "foo.py").write_text(
            "\n" * 41 + "query = 'SELECT * FROM users WHERE id = ' + uid\n"
        )
        result = adapter.review_prompt(prompt_with_repo)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1

    def test_streaming_accumulates_chunks(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Streaming chunks are accumulated into full response."""
        calls: list[int] = []

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            calls.append(1)
            if len(calls) == 1:
                return _FakeStreamingResponse(
                    TestHelpers.make_action_json("list_directory", ".")
                )
            return _FakeStreamingResponse(
                TestHelpers.make_verdict_json("APPROVED", issues=[])
            )

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "file1.py\nfile2.py",
        )

        result = adapter.review_prompt(prompt_with_repo)
        assert result.verdict == ReviewVerdict.APPROVED
        assert len(result.items) == 0

    def test_raises_on_max_turns_exceeded(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Returns CodeReview with APPROVED verdict when max turns exceeded."""

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                TestHelpers.make_action_json("list_directory", ".")
            )

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "file1.py\nfile2.py",
        )

        # Should return a CodeReview with APPROVED verdict instead of raising error
        result = adapter.review_prompt(prompt_with_repo)
        assert result.verdict == ReviewVerdict.APPROVED
        assert result.reason == "No issues found across all review phases."
        assert len(result.items) == 0

    def test_dumps_conversation_on_exhaustion(
        self,
        monkeypatch: pytest.MonkeyPatch,
        adapter: OllamaExploratoryChatAdapter,
        prompt_with_repo: ComposedPrompt,
    ) -> None:
        """Max-turns exhaustion dumps conversation to a temp file."""
        # Save the real mkstemp before mocking
        real_mkstemp = tempfile.mkstemp
        written_paths: list[str] = []

        def fake_mkstemp(suffix: str = "", **kwargs: Any) -> tuple[int, str]:
            fd, path = real_mkstemp(suffix=suffix, **kwargs)
            written_paths.append(path)
            return fd, path

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                TestHelpers.make_action_json("list_directory", ".")
            )

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama.ollama_exploratory_chat_adapter.ExplorationToolService.execute",
            lambda self, action, args: "file1.py\nfile2.py",
        )
        monkeypatch.setattr(tempfile, "mkstemp", fake_mkstemp)

        # Should return a CodeReview instead of raising error
        result = adapter.review_prompt(prompt_with_repo)
        assert result.verdict == ReviewVerdict.APPROVED
        assert result.reason == "No issues found across all review phases."
        assert len(result.items) == 0

        # Verify conversation was dumped to temp file (multiple times due to retries)
        assert len(written_paths) >= 1
        # Check that at least one dump contains the expected content
        dumped = json.loads(Path(written_paths[0]).read_text())
        assert isinstance(dumped, list)
        assert any("list_directory" in json.dumps(m) for m in dumped)
        # Clean up all dumped files
        for path in written_paths:
            Path(path).unlink()