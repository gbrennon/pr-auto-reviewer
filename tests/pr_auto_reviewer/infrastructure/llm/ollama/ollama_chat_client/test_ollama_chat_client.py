from ._helpers import *


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
            "pr_auto_reviewer.infrastructure.llm.ollama.ollama_chat_client.time.sleep",
            lambda _: None,
        )

        client = OllamaChatClient(model="code-review:latest", max_retries=2)
        with pytest.raises(LlmUnavailableError):
            client.send([ConversationMessage(role="user", content="hi")])
        assert calls == 2

