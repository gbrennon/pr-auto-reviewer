from ._helpers import *


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

