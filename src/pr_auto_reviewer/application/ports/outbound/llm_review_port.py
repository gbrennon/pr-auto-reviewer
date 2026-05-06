"""LlmReviewPort — send a diff + context to an LLM and receive a CodeReview."""

from typing import Protocol

from ....domain.value_objects.pull_request_diff import PullRequestDiff
from ....domain.value_objects.repository_context import RepositoryContext
from ....domain.value_objects.code_review import CodeReview


class LlmReviewPort(Protocol):
    def review(self, diff: PullRequestDiff, context: RepositoryContext) -> CodeReview:
        ...
