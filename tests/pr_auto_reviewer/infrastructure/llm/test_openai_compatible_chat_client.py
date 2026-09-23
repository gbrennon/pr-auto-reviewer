"""Tests for the shared OpenAI-compatible streaming chat client."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.infrastructure.llm.openai_compatible_chat_client import (
    OpenAiCompatibleChatClient,
)


class _FakeStreamingResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self.encoding: str | None = None

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self, decode_unicode: bool = True) -> Iterator[str]:
        yield from self._lines


class TestOpenAiCompatibleChatClient:
    def test_send_uses_one_v1_suffix_and_accumulates_sse_content(self) -> None:
        calls: list[tuple[str, dict[str, Any], bool]] = []
        lines = [
            'data: {"choices": [{"delta": {"content": "Hello "}}]}',
            'data: {"choices": [{"delta": {"content": "world"}}]}',
            "data: [DONE]",
        ]

        def fake_post(
            url: str,
            *,
            json: dict[str, Any],
            timeout: int,
            stream: bool,
        ) -> _FakeStreamingResponse:
            calls.append((url, json, stream))
            return _FakeStreamingResponse(lines)

        client = OpenAiCompatibleChatClient(
            host="http://localhost:11434/v1/",
            model="qwen3",
            http_post=fake_post,
        )

        result = client.send([ConversationMessage(role="user", content="hi")])

        assert result == "Hello world"
        assert calls[0][0] == "http://localhost:11434/v1/chat/completions"
        assert calls[0][1]["model"] == "qwen3"
        assert calls[0][2] is True

    def test_send_falls_back_to_reasoning_content(self) -> None:
        lines = [
            'data: {"choices": [{"delta": '
            '{"reasoning_content": "thinking"}}]}',
            "data: [DONE]",
        ]

        def fake_post(*_args: Any, **_kwargs: Any) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(lines)

        client = OpenAiCompatibleChatClient(http_post=fake_post)

        result = client.send([ConversationMessage(role="user", content="hi")])

        assert result == "thinking"
