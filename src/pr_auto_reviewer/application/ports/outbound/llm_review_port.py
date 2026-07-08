"""LlmReviewPort — send a prompt or diff+context to an LLM and receive a CodeReview."""

from typing import Protocol

from ....domain.value_objects.pull_request_diff import PullRequestDiff
from ....domain.value_objects.repository_context import RepositoryContext
from ....domain.value_objects.code_review import CodeReview
from ....domain.fragments.entities.composed_prompt import ComposedPrompt

class LlmReviewPort(Protocol):
    def review(self, diff: PullRequestDiff, context: RepositoryContext) -> CodeReview:
        """Deprecated: use :meth:`review_prompt` with fragment-based composition.

        Implementations should delegate to the fragment-based flow
        internally when possible.
        """
        ...

    def review_prompt(self, prompt: ComposedPrompt) -> CodeReview:
        """Send an already-composed prompt to the LLM and return a CodeReview.

        Args:
            prompt: A fully assembled prompt ready for LLM consumption.

        Returns:
            The parsed code review.
        """
        ...
