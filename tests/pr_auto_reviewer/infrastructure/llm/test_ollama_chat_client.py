"""Tests for OllamaChatClient streaming behavior.

These tests cover the streaming JSON parser regressions:
1. Streams are decoded as UTF-8 regardless of the response charset
   (missing charset used to fall back to ISO-8859-1, splitting JSON
   lines on NEL bytes and aborting the whole request).
2. A single unparseable line is skipped instead of retrying the entire
   conversation.
"""

from __future__ import annotations

import json
from typing import Any, Iterator

import pytest
import requests

from pr_auto_reviewer.domain.agent.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.infrastructure.llm.ollama_chat_client import (
    OllamaChatClient,
)


class _FakeStreamingResponse:
    """Fake ``requests.Response`` mirroring requests' decode-then-split.

    ``iter_lines(decode_unicode=True)`` decodes the raw body using
    ``self.encoding`` (ISO-8859-1 when unset, like requests) and then
    splits on line boundaries — faithfully reproducing the NEL-split
    corruption that used to break ``json.loads``.
    """

    def __init__(self, raw_body: bytes, *, status_code: int = 200) -> None:
        self._raw_body = raw_body
        self.status_code = status_code
        self.encoding: str | None = None

    def raise_for_status(self) -> None:
        pass

    def iter_lines(self, decode_unicode: bool) -> Iterator[str]:
        text = self._raw_body.decode(self.encoding or "iso-8859-1")
        for line in text.splitlines():
            if line:
                yield line


def _json_line(message: dict[str, Any]) -> bytes:
    return json.dumps(
        {"message": message}, ensure_ascii=False
    ).encode("utf-8")


class TestOllamaChatClient:
    def test_send_decodes_stream_as_utf8(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-ASCII chars whose UTF-8 bytes contain NEL are decoded correctly."""
        content = "PASS \u2105"
        raw = (
            _json_line({"content": content, "done": False})
            + b"\n"
            + _json_line({"content": "", "done": True})
            + b"\n"
        )
        response = _FakeStreamingResponse(raw)
        monkeypatch.setattr(requests, "post", lambda *a, **k: response)

        client = OllamaChatClient(model="code-review:latest", max_retries=2)
        result = client.send([ConversationMessage(role="user", content="hi")])

        assert result == content
        assert response.encoding == "utf-8"

    def test_send_skips_unparseable_line_without_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unparseable line is skipped; the request is not retried."""
        bad = b'{"message":{"content": "truncated'
        good = _json_line({"content": "hello", "done": True})
        response = _FakeStreamingResponse(bad + b"\n" + good + b"\n")
        calls = 0

        def fake_post(*args: object, **kwargs: object) -> _FakeStreamingResponse:
            nonlocal calls
            calls += 1
            return response

        monkeypatch.setattr(requests, "post", fake_post)

        client = OllamaChatClient(model="code-review:latest", max_retries=3)
        result = client.send([ConversationMessage(role="user", content="hi")])

        assert result == "hello"
        assert calls == 1

    def test_send_retries_on_network_error_then_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Request failures still retry and escalate to LlmUnavailableError."""
        calls = 0

        def fake_post(*args: object, **kwargs: object) -> Any:
            nonlocal calls
            calls += 1
            raise requests.ConnectionError("boom")

        monkeypatch.setattr(requests, "post", fake_post)
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.llm.ollama_chat_client.time.sleep",
            lambda _: None,
        )

        client = OllamaChatClient(model="code-review:latest", max_retries=2)
        with pytest.raises(LlmUnavailableError):
            client.send([ConversationMessage(role="user", content="hi")])
        assert calls == 2
