"""Tests for Ollama streaming LLM adapter using fake."""

from __future__ import annotations

import pytest

from tests.fakes.fake_ollama_streaming_llm_adapter import FakeOllamaStreamingLlmAdapter
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext


class TestFakeOllamaStreamingLlmAdapter:
    """Tests using the fake Ollama streaming LLM adapter."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake adapter can be instantiated."""
        fake = FakeOllamaStreamingLlmAdapter()
        assert fake is not None

    def test_fake_review_prompt(self) -> None:
        """Fake review_prompt returns CodeReview without calling Ollama."""
        from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt

        fake = FakeOllamaStreamingLlmAdapter()
        prompt = ComposedPrompt(
            content="test prompt",
            fragments_used=[],
            total_tokens=100,
        )
        review = fake.review_prompt(prompt)
        assert isinstance(review, CodeReview)
        assert fake.review_prompt_calls  # Should have been called

    def test_fake_review(self) -> None:
        """Fake review returns CodeReview without calling Ollama."""
        fake = FakeOllamaStreamingLlmAdapter()
        from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
        from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext

        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha="abc123",
            diff_content="diff --git a/test.py b/test.py\n+new line\n",
        )
        ctx = RepositoryContext(
            architecture_hint="python",
            conventions=None,
            repository_structure="standard",
            pr_title="Test PR",
            pr_description="Test description",
            python_version="3.12",
        )
        review = fake.review(diff, ctx)
        assert isinstance(review, CodeReview)
        assert fake.review_calls  # Should have been called