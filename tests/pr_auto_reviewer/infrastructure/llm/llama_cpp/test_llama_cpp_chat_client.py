"""Tests for LlamaCppChatClient."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.exceptions.review_budget_exhausted_error import (
    ReviewBudgetExhaustedError,
)
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.infrastructure.llm.llama_cpp.llama_cpp_chat_client import (
    LlamaCppChatClient,
)


class _FakeStreamingResponse:
    def __init__(self, lines: list[str], status_code: int = 200) -> None:
        self._lines = lines
        self.status_code = status_code
        self.encoding: str | None = None

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"Status {self.status_code}")

    def iter_lines(self, decode_unicode: bool = True) -> Iterator[str]:
        yield from self._lines


class TestLlamaCppChatClient:
    def test_send_accumulates_streamed_sse_content(self) -> None:
        lines = [
            'data: {"choices": [{"delta": {"content": "Hello "}}]}',
            'data: {"choices": [{"delta": {"content": "world"}}]}',
            "data: [DONE]",
        ]

        def fake_post(*_args: Any, **_kwargs: Any) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(lines)

        client = LlamaCppChatClient(http_post=fake_post)
        result = client.send([ConversationMessage(role="user", content="hi")])

        assert result == "Hello world"

    def test_send_falls_back_to_reasoning_content(self) -> None:
        lines = [
            'data: {"choices": [{"delta": {"reasoning_content": "Deep thought"}}]}',
            "data: [DONE]",
        ]

        def fake_post(*_args: Any, **_kwargs: Any) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(lines)

        client = LlamaCppChatClient(http_post=fake_post)
        result = client.send([ConversationMessage(role="user", content="hi")])

        assert result == "Deep thought"

    def test_send_skips_unparseable_lines(self) -> None:
        lines = [
            "data: not valid json",
            'data: {"choices": [{"delta": {"content": "recovered"}}]}',
            "data: [DONE]",
        ]

        def fake_post(*_args: Any, **_kwargs: Any) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(lines)

        client = LlamaCppChatClient(http_post=fake_post)
        result = client.send([ConversationMessage(role="user", content="hi")])

        assert result == "recovered"

    def test_budget_exhausted_raises_error(self) -> None:
        lines = [
            'data: {"choices": [{"delta": {"content": "ok"}}]}',
            "data: [DONE]",
        ]

        def fake_post(*_args: Any, **_kwargs: Any) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(lines)

        client = LlamaCppChatClient(max_llm_calls=1, http_post=fake_post)
        msg = [ConversationMessage(role="user", content="hi")]

        assert client.send(msg) == "ok"
        with pytest.raises(ReviewBudgetExhaustedError):
            client.send(msg)

    def test_send_retries_on_network_error_then_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = 0

        def fake_post(*_args: Any, **_kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            raise requests.ConnectionError("Connection failed")

        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.base_chat_client.time.sleep",
            lambda _: None,
        )
        client = LlamaCppChatClient(max_retries=3, http_post=fake_post)
        with pytest.raises(LlmUnavailableError):
            client.send([ConversationMessage(role="user", content="hi")])

        assert calls == 3
