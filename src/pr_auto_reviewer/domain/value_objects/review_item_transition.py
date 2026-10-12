"""Immutable lifecycle transition for a review item."""

from __future__ import annotations

from dataclasses import dataclass

from .review_item_status import ReviewItemStatus


@dataclass(frozen=True)
class ReviewItemTransition:
    """Record one observed review-item status transition."""

    from_status: ReviewItemStatus | None
    to_status: ReviewItemStatus
    commit_sha: str
    explanation: str

    def __post_init__(self) -> None:
        """Normalize status values at the domain boundary."""
        if self.from_status is not None:
            object.__setattr__(
                self, "from_status", ReviewItemStatus(self.from_status)
            )
        object.__setattr__(self, "to_status", ReviewItemStatus(self.to_status))
        commit_sha = str(self.commit_sha)
        if not commit_sha:
            raise ValueError("Review item transition commit SHA must be non-empty")
        object.__setattr__(self, "commit_sha", commit_sha)
