"""Tests for Ollama streaming chat implementation using fake."""

from __future__ import annotations

import pytest
import asyncio

from tests.fakes.fake_ollama_streaming_chat_impl import FakeOllamaStreamingChatImpl


class TestFakeOllamaStreamingChatImpl:
    """Tests using the fake Ollama streaming chat implementation."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake client can be instantiated."""
        fake = FakeOllamaStreamingChatImpl(model="test-model", host="http://localhost:11434")
        assert fake._model == "test-model"

    def test_fake_send_message(self) -> None:
        """Fake send_message returns response without HTTP calls."""
        fake = FakeOllamaStreamingChatImpl(model="test-model", host="http://localhost:11434")
        result = fake.send_message("test prompt")
        assert '{"verdict"' in result
        assert len(fake.send_message_calls) == 1

    @pytest.mark.asyncio
    async def test_fake_start_review(self) -> None:
        """Fake start_review yields turns without HTTP calls."""
        fake = FakeOllamaStreamingChatImpl(model="test-model", host="http://localhost:11434")
        turns = []
        async for turn in fake.start_review("repo", 1, "diff"):
            turns.append(turn)
        assert len(turns) == 1
        assert turns[0]["kind"] == "complete"
        assert "parsed" in turns[0]

    @pytest.mark.asyncio
    async def test_fake_start_review_records_call(self) -> None:
        """Fake start_review records the call parameters."""
        fake = FakeOllamaStreamingChatImpl(model="test-model", host="http://localhost:11434")
        turns = []
        async for turn in fake.start_review("my/repo", 42, "some diff"):
            turns.append(turn)
        assert len(fake.start_review_calls) == 1
        repo, pr_number, diff = fake.start_review_calls[0]
        assert repo == "my/repo"
        assert pr_number == 42