"""Behavioral tests for OllamaStreamingChatClient over a replaying httpx transport."""

import json

import pytest

from pr_auto_reviewer.infrastructure.llm.ollama.ollama_streaming_chat_impl import (
    OllamaStreamingChatClient,
)


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


def _patch_httpx(monkeypatch, lines, error=None) -> dict:
    holder: dict = {}
    factory = lambda **kwargs: holder.setdefault("client", _FakeHttpxClient(lines, error=error, **kwargs))
    monkeypatch.setattr("httpx.Client", factory)
    return holder


def _client(*, model="code-review:latest", host="http://localhost:11434") -> OllamaStreamingChatClient:
    return OllamaStreamingChatClient(model=model, host=host)


class TestSendMessage:
    """Exercises the blocking single-message stream."""

    def test_send_message_when_stream_chunks_then_accumulates(self, monkeypatch) -> None:
        _patch_httpx(
            monkeypatch,
            [
                '{"message":{"content":"chunk1 "},"done":false}',
                '{"message":{"content":"chunk2"},"done":true}',
            ],
        )

        result = _client().send_message("review this")

        assert result == "chunk1 chunk2"

    def test_send_message_posts_chat_body(self, monkeypatch) -> None:
        holder = _patch_httpx(monkeypatch, ['{"message":{"content":"x"},"done":false}'])

        _client().send_message("review this")

        sent = holder["client"].sent[0]
        assert sent["method"] == "POST"
        assert sent["url"] == "http://localhost:11434/api/chat"
        body = sent["json"]
        assert body["model"] == "code-review:latest"
        assert body["stream"] is True
        assert body["messages"][-1] == {"role": "user", "content": "review this"}
        json.loads(body["format"])

    def test_send_message_without_history_then_system_preamble(self, monkeypatch) -> None:
        holder = _patch_httpx(monkeypatch, ['{"message":{"content":"x"},"done":true}'])

        _client().send_message("review this")

        messages = holder["client"].sent[0]["json"]["messages"]
        assert messages[0]["role"] == "system"
        assert messages[1] == {"role": "user", "content": "review this"}

    def test_send_message_with_history_then_preserves_turns(self, monkeypatch) -> None:
        holder = _patch_httpx(monkeypatch, ['{"message":{"content":"x"},"done":true}'])
        history = [{"role": "user", "content": "prior"}]

        _client().send_message("review this", conversation_history=history)

        messages = holder["client"].sent[0]["json"]["messages"]
        assert messages[0] == {"role": "user", "content": "prior"}

    def test_send_message_when_malformed_line_then_skipped(self, monkeypatch) -> None:
        _patch_httpx(
            monkeypatch,
            ["not-json", "", '{"message":{"content":"ok"},"done":true}'],
        )

        result = _client().send_message("review this")

        assert result == "ok"

    def test_send_message_when_done_then_stops_reading(self, monkeypatch) -> None:
        _patch_httpx(
            monkeypatch,
            [
                '{"message":{"content":"a"},"done":false}',
                '{"message":{"content":""},"done":true}',
                '{"message":{"content":"never-read"},"done":false}',
            ],
        )

        result = _client().send_message("review this")

        assert result == "a"


class TestStartReview:
    """Exercises the async multi-turn review stream."""

    @pytest.mark.asyncio
    async def test_start_review_when_valid_json_then_yields_complete_turn(self, monkeypatch) -> None:
        _patch_httpx(
            monkeypatch,
            [
                '{"message":{"content":"{\\"verdict\\": \\"approved\\"}"},"done":true}',
            ],
        )

        client = _client()
        turns = [turn async for turn in client.start_review("/repo", 1, "diff")]

        assert len(turns) == 1
        assert turns[0]["kind"] == "complete"
        assert turns[0]["parsed"]["verdict"] == "approved"

    @pytest.mark.asyncio
    async def test_start_review_when_prose_then_parse_fallback(self, monkeypatch) -> None:
        _patch_httpx(monkeypatch, ['{"message":{"content":"hello world"},"done":true}'])

        client = _client()
        turns = [turn async for turn in client.start_review("/repo", 1, "diff")]

        assert turns[0]["kind"] == "complete"
        assert turns[0]["parsed"]["verdict"] == "commented"
        assert "failed to parse" in turns[0]["parsed"]["reason"]

    @pytest.mark.asyncio
    async def test_start_review_when_malformed_line_then_skipped(self, monkeypatch) -> None:
        _patch_httpx(
            monkeypatch,
            [
                "not-json",
                '{"message":{"content":"{\\"verdict\\": \\"commented\\"}"},"done":true}',
            ],
        )

        client = _client()
        turns = [turn async for turn in client.start_review("/repo", 1, "diff")]

        assert turns[0]["parsed"]["verdict"] == "commented"

    @pytest.mark.asyncio
    async def test_start_review_when_empty_line_then_skipped(self, monkeypatch) -> None:
        _patch_httpx(
            monkeypatch,
            [
                "",
                '{"message":{"content":"{\\"verdict\\": \\"commented\\"}"},"done":true}',
            ],
        )

        client = _client()
        turns = [turn async for turn in client.start_review("/repo", 1, "diff")]

        assert turns[0]["parsed"]["verdict"] == "commented"

    @pytest.mark.asyncio
    async def test_start_review_posts_prompt_body(self, monkeypatch) -> None:
        holder = _patch_httpx(monkeypatch, ['{"message":{"content":"x"},"done":true}'])

        client = _client()
        async for _ in client.start_review("/repo", 7, "the diff"):
            pass

        sent = holder["client"].sent[0]
        body = sent["json"]
        assert body["model"] == "code-review:latest"
        assert body["messages"][0]["role"] == "user"
        assert "the diff" in body["messages"][0]["content"]
        assert sent["url"] == "http://localhost:11434/api/chat"


class TestClientMetadata:
    """Exercises the client accessor properties."""

    def test_model_property_returns_model(self) -> None:
        assert _client(model="code-review:latest").model == "code-review:latest"

    def test_host_property_strips_trailing_slash(self) -> None:
        assert _client(host="http://localhost:11434/").host == "http://localhost:11434"

    def test_json_schema_is_object(self) -> None:
        assert _client().json_schema["type"] == "object"


class TestClassifyTurn:
    """Exercises the per-line turn classifier."""

    def test_classify_when_tool_calls_then_tool_call(self) -> None:
        assert (
            _client()._classify_turn("", {"tool_calls": [{"function": {"name": "read_file"}}]}, False)
            == "tool_call"
        )

    def test_classify_when_verdict_marker_then_verdict(self) -> None:
        assert _client()._classify_turn("verdict: approved", {}, False) == "verdict"

    def test_classify_when_verbatim_verdict_then_verdict(self) -> None:
        assert _client()._classify_turn("approved", {}, False) == "verdict"

    def test_classify_when_json_object_then_complete(self) -> None:
        assert _client()._classify_turn('{"a": 1}', {}, False) == "complete"

    def test_classify_when_json_array_then_complete(self) -> None:
        assert _client()._classify_turn("[1, 2]", {}, False) == "complete"

    def test_classify_when_other_then_unparseable(self) -> None:
        assert _client()._classify_turn("filler", {}, False) == "unparseable"

    def test_classify_when_verdict_seen_then_verdict_not_reclassified(self) -> None:
        assert _client()._classify_turn("verdict: approved", {}, True) == "unparseable"