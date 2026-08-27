"""Shared helpers, fixtures, and imports for the split test modules."""

import json

import pytest

from pr_auto_reviewer.infrastructure.llm.ollama.ollama_streaming_chat_impl import (
    OllamaStreamingChatClient,
)


def _patch_httpx(monkeypatch, lines, error=None) -> dict:
    holder: dict = {}
    factory = lambda **kwargs: holder.setdefault("client", _FakeHttpxClient(lines, error=error, **kwargs))
    monkeypatch.setattr("httpx.Client", factory)
    return holder


def _client(*, model="code-review:latest", host="http://localhost:11434") -> OllamaStreamingChatClient:
    return OllamaStreamingChatClient(model=model, host=host)


__all__ = ['OllamaStreamingChatClient', '_FakeHttpxClient', '_FakeStreamResponse', '_client', '_patch_httpx', 'json', 'pytest']


class _FakeStreamResponse:
    def __init__(self, lines, error=None) -> None:
        self._lines = list(lines)
        self._error = error

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def raise_for_status(self) -> None:
        if self._error:
            raise self._error

    def iter_lines(self):
        yield from self._lines


class _FakeHttpxClient:
    def __init__(self, lines, error=None, **kwargs) -> None:
        self._lines = list(lines)
        self._error = error
        self.sent: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def stream(self, method, url, *, json=None, headers=None):
        self.sent.append({"method": method, "url": url, "json": json, "headers": headers})
        return _FakeStreamResponse(self._lines, self._error)
