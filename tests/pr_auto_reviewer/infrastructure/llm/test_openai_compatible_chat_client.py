"""Tests for the shared OpenAI-compatible streaming chat client."""

from __future__ import annotations

import logging
from typing import Any


import pytest
import requests

from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
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

    def iter_lines(self, decode_unicode: bool = True) -> list[str]:
        return self._lines





class TestOpenAiCompatibleChatClient:
    def test_send_keeps_default_context_small_for_interactive_reviews(self) -> None:
        payloads: list[dict[str, Any]] = []

        def fake_post(*_args: Any, **kwargs: Any) -> _FakeStreamingResponse:
            payloads.append(kwargs["json"])
            return _FakeStreamingResponse(["data: [DONE]"])

        messages = [
            ConversationMessage(role="system", content="system"),
            ConversationMessage(role="user", content="request"),
            *[
                message
                for index in range(30)
                for message in (
                    ConversationMessage(
                        role="assistant", content=f"assistant {index} " + "x" * 2000
                    ),
                    ConversationMessage(
                        role="user", content=f"result {index} " + "y" * 2000
                    ),
                )
            ],
        ]
        client = OpenAiCompatibleChatClient(http_post=fake_post)

        client.send(messages)

        assert len(payloads[0]["messages"]) <= 35

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

    def test_send_logs_http_error_response_body(self, caplog: Any) -> None:
        response = requests.Response()
        response.status_code = 400
        response.url = "http://localhost:11434/v1/chat/completions"
        response._content = b'{"error":{"message":"context size exceeded"}}'

        def fake_post(*_args: Any, **_kwargs: Any) -> requests.Response:
            return response

        client = OpenAiCompatibleChatClient(
            http_post=fake_post,
            max_retries=1,
        )

        with caplog.at_level(logging.ERROR):
            with pytest.raises(LlmUnavailableError):
                client.send([ConversationMessage(role="user", content="hi")])

        assert "context size exceeded" in caplog.text
    def test_send_bounds_history_before_http_dispatch(self) -> None:
        messages = [
            ConversationMessage(role="system", content="s" * 1000),
            ConversationMessage(role="user", content="u" * 1000),
        ]
        messages.extend(
            message
            for turn in range(20)
            for message in (
                ConversationMessage(
                    role="assistant",
                    content=f"assistant-{turn} " + "a" * 7000,
                ),
                ConversationMessage(
                    role="user",
                    content=f"tool-{turn} " + "r" * 7000,
                ),
            )
        )
        requests_seen: list[dict[str, Any]] = []

        def fake_post(
            _url: str,
            *,
            json: dict[str, Any],
            **_kwargs: Any,
        ) -> _FakeStreamingResponse:
            requests_seen.append(json)
            return _FakeStreamingResponse(
                ['data: {"choices": [{"delta": {"content": "ok"}}]}']
            )

        client = OpenAiCompatibleChatClient(http_post=fake_post)

        result = client.send(messages)

        sent_messages = requests_seen[0]["messages"]
        assert result == "ok"
        assert len(sent_messages) < len(messages)
        assert sent_messages[:2] == [
            {"role": "system", "content": "s" * 1000},
            {"role": "user", "content": "u" * 1000},
        ]
        assert "earlier messages omitted" in sent_messages[2]["content"]
        retained_messages = sent_messages[3:]
        assert retained_messages[0]["role"] == "assistant"
        assert all(
            retained_messages[index]["role"] != retained_messages[index + 1]["role"]
            for index in range(len(retained_messages) - 1)
        )
