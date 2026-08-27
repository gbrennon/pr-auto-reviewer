from ._helpers import *


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

