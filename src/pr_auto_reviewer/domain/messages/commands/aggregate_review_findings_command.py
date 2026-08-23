"""AggregateReviewFindingsCommand — input for merging review findings across phases."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult


@dataclass(frozen=True)
class AggregateReviewFindingsCommand:
    """Command to deduplicate and merge review items into a CodeReview.

    ``suggestions_phase_result`` selects which phase's ``llm_suggestions``
    feed the final review's ``suggestions``; when None, ``phase_result``
    is used as the suggestion source too.
    """

    items: list[ReviewItem]
    model_used: str
    phase_result: PhaseResult | None = None
    suggestions_phase_result: PhaseResult | None = None
    repo_name: str = ""
    pr_id: str = ""