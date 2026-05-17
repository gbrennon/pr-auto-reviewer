"""ReviewContextFactoryPort — builds a composed prompt from PR data."""

from __future__ import annotations

from typing import Protocol

from ....domain.fragments.entities.composed_prompt import ComposedPrompt
from ....domain.value_objects.pull_request_diff import PullRequestDiff
from ....domain.value_objects.pull_request_id import PullRequestId


class ReviewContextFactoryPort(Protocol):
    """Outbound port that encapsulates repository-context fetching,
    language detection, context serialisation, and fragment-based
    prompt composition into a single call.

    Replaces the separate ``RepositoryContextPort`` +
    ``ComposeReviewPromptPort`` data clump.
    """

    def build(
        self,
        pr_id: PullRequestId,
        diff: PullRequestDiff,
        pr_title: str | None = None,
        pr_description: str | None = None,
    ) -> ComposedPrompt:
        """Fetch repo context, build ReviewContext, compose fragments.

        Args:
            pr_id: The pull request identifier.
            diff: The diff to review.
            pr_title: Optional PR title for context.
            pr_description: Optional PR description for context.

        Returns:
            A fully assembled prompt ready for LLM consumption.
        """
        ...
