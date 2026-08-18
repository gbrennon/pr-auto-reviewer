"""Tests for Ollama streaming chat ABC using fake."""

from __future__ import annotations

import pytest
import asyncio

from tests.fakes.fake_ollama_streaming_chat_abc import (
    FakeOllamaStreamingChatABC,
    FakeOllamaReviewStream,
)


class TestFakeOllamaStreamingChatABC:
    """Tests using the fake Ollama streaming chat ABC."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake ABC can be instantiated."""
        fake = FakeOllamaStreamingChatABC()
        assert fake.model == "test-model"
        assert fake.host == "http://localhost:11434"

    def test_fake_send_message(self) -> None:
        """Fake send_message returns expected response."""
        fake = FakeOllamaStreamingChatABC()
        result = fake.send_message("test prompt")
        assert '{"verdict"' in result

    def test_fake_start_review(self) -> None:
        """Fake start_review returns expected stream."""
        fake = FakeOllamaStreamingChatABC()
        result = asyncio.run(fake.start_review("repo", 1, "diff"))
        assert "commented" in result

    def test_fake_parse_streaming_response(self) -> None:
        """Fake parse_streaming_response handles JSON."""
        fake = FakeOllamaStreamingChatABC()
        items, metadata = fake.parse_streaming_response(
            ['{"verdict": "approved"}'], "test-model"
        )
        assert metadata["verdict"] == "approved"

    def test_fake_review_stream(self) -> None:
        """Fake review stream advance method."""
        stream = FakeOllamaReviewStream()
        stream.advance('{"verdict": "commented"}', "complete")
        assert stream.kind == "complete"
        assert stream.parsed is not None