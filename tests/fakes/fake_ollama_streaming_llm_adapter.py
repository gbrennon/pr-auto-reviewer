"""Fake Ollama streaming LLM adapter for tests."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)


class FakeOllamaStreamingLlmAdapter(LlmReviewPort):
    """Fake adapter implementing LlmReviewPort for testing."""

    def __init__(self) -> None:
        self._parser = ReviewResponseParser()
        self.review_prompt_calls: list[tuple[ComposedPrompt, str]] = []
        self.review_calls: list[tuple[PullRequestDiff, RepositoryContext]] = []
        self._model = "test-model"

    def review_prompt(self, prompt: ComposedPrompt) -> CodeReview:
        """Send prompt to fake Ollama and return fake CodeReview."""
        self.review_prompt_calls.append((prompt, "code-review:latest"))
        from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
        from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
        from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext

        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="test/repo", number=1),
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
        review = CodeReview(
            verdict="commented",
            reason="test reason",
            summary="test summary",
            model_used="code-review:latest",
        )
        self.review_calls.append((diff, ctx))
        return review

    def review(
        self,
        diff: PullRequestDiff,
        context: RepositoryContext,
    ) -> CodeReview:
        """Fake review method."""
        self.review_calls.append((diff, context))
        from pr_auto_reviewer.domain.value_objects.code_review import CodeReview

        return CodeReview(
            verdict="commented",
            reason="test reason",
            summary="test summary",
            model_used="code-review:latest",
        )