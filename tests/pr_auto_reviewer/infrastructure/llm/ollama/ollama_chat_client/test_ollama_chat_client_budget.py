from ._helpers import *


class TestOllamaChatClientBudget:
    def _ok_response(self) -> _FakeStreamingResponse:
        raw = _json_line({"content": "ok", "done": True}) + b"\n"
        return _FakeStreamingResponse(raw)

    def test_budget_exhausted_raises_before_sending_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No HTTP request is made once the call budget is consumed."""
        calls = 0

        def fake_post(*args: object, **kwargs: object) -> Any:
            nonlocal calls
            calls += 1
            return self._ok_response()

        monkeypatch.setattr(requests, "post", fake_post)
        client = OllamaChatClient(
            model="code-review:latest", max_llm_calls=1
        )
        message = [ConversationMessage(role="user", content="hi")]

        client.send(message)
        with pytest.raises(ReviewBudgetExhaustedError):
            client.send(message)

        assert calls == 1

    def test_unlimited_budget_never_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without a budget the client behaves as before."""
        monkeypatch.setattr(
            requests, "post", lambda *a, **k: self._ok_response()
        )
        client = OllamaChatClient(model="code-review:latest")
        message = [ConversationMessage(role="user", content="hi")]

        for _ in range(3):
            assert client.send(message) == "ok"

