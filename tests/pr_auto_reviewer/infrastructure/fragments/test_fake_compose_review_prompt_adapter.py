"""Tests for ComposeReviewPromptAdapter using fake."""

from __future__ import annotations

import pytest

from tests.fakes.fake_compose_review_prompt_adapter import FakeComposeReviewPromptAdapter


class TestFakeComposeReviewPromptAdapter:
    """Tests using the fake ComposeReviewPromptAdapter."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake compose prompt adapter can be instantiated."""
        fake = FakeComposeReviewPromptAdapter()
        assert fake is not None

    def test_fake_compose(self) -> None:
        """Fake compose returns configured prompt without LLM calls."""
        fake = FakeComposeReviewPromptAdapter()
        schema = {"type": "object", "properties": {"verdict": {"type": "string"}}}
        result = fake.compose("diff content", schema)
        assert "code-review:latest" in result
        assert len(fake.compose_calls) == 1