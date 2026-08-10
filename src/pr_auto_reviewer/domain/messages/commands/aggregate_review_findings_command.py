"""AggregateReviewFindingsCommand — input for merging review findings across phases."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
from pr_auto_reviewer.domain.entities.review_item import ReviewItem


@dataclass(frozen=True)
class AggregateReviewFindingsCommand:
    """Command to deduplicate and merge review items into a CodeReview."""

    items: list[ReviewItem]
    phase_result: PhaseResult | None = None
    model_used: str = ""
