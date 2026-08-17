"""Fake LLM reviewer for tests."""

from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext


class FakeLlmReview:
    def __init__(self, review: CodeReview) -> None:
        self._review = review
        self.review_calls: list[tuple[PullRequestDiff, RepositoryContext]] = []
        self.review_prompt_calls: list = []

    def review(self, diff: PullRequestDiff, ctx: RepositoryContext) -> CodeReview:
        self.review_calls.append((diff, ctx))
        return self._review

    def review_prompt(self, prompt) -> CodeReview:
        self.review_prompt_calls.append(prompt)
        return self._review