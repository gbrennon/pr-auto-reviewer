"""Fake LLM reviewer for tests."""

from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext


class FakeLlmReview:
    def __init__(self, review: CodeReview) -> None:
        self._review = review
        self.review_calls: list[tuple[PullRequestDiff, RepositoryContext]] = []
        self.review_prompt_calls: list = []

    def review(self, diff: PullRequestDiff, context: RepositoryContext) -> CodeReview:
        self.review_calls.append((diff, context))
        return self._review

    def review_prompt(self, prompt: ComposedPrompt) -> CodeReview:
        self.review_prompt_calls.append(prompt)
        return self._review
