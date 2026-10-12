"""Immutable proof-gated lifecycle projection for a review item."""

from __future__ import annotations

from dataclasses import dataclass

from .review_item_status import ReviewItemStatus
from .review_item_transition import ReviewItemTransition


@dataclass(frozen=True)
class ReviewItemLifecycle:
    """Status history for one immutable review-item evidence record."""

    item_id: str
    status: ReviewItemStatus
    first_seen_sha: str
    last_audited_sha: str
    status_explanation: str
    transitions: tuple[ReviewItemTransition, ...] = ()

    def __post_init__(self) -> None:
        """Normalize lifecycle status, SHAs, and transition collection."""
        object.__setattr__(self, "status", ReviewItemStatus(self.status))
        object.__setattr__(self, "transitions", tuple(self.transitions))
        object.__setattr__(self, "first_seen_sha", str(self.first_seen_sha))
        object.__setattr__(self, "last_audited_sha", str(self.last_audited_sha))
        if not self.item_id:
            raise ValueError("Review item lifecycle ID must be non-empty")
        if not self.first_seen_sha or not self.last_audited_sha:
            raise ValueError("Review item lifecycle SHA values must be non-empty")

    @classmethod
    def first_appearance(
        cls,
        item_id: str,
        commit_sha: str,
        explanation: str = "",
    ) -> ReviewItemLifecycle:
        """Create a CREATED lifecycle at the item's first appearance."""
        commit_sha = str(commit_sha)
        transition = ReviewItemTransition(
            from_status=None,
            to_status=ReviewItemStatus.CREATED,
            commit_sha=commit_sha,
            explanation=explanation,
        )
        return cls(
            item_id=item_id,
            status=ReviewItemStatus.CREATED,
            first_seen_sha=commit_sha,
            last_audited_sha=commit_sha,
            status_explanation=explanation,
            transitions=(transition,),
        )

    @property
    def is_active(self) -> bool:
        """Return whether this lifecycle can receive a resolving audit."""
        return self.status.is_active

    @property
    def is_terminal(self) -> bool:
        """Return whether this lifecycle can never be reopened."""
        return self.status.is_terminal

    def audit(
        self,
        commit_sha: str,
        present: bool = True,
        proof: bool = False,
        explanation: str = "",
    ) -> ReviewItemLifecycle:
        """Audit this lifecycle, resolving it only with positive proof.

        Presence without proof keeps an active item open. Terminal lifecycles
        retain their terminal status regardless of later audit observations.
        """
        commit_sha = str(commit_sha)
        if self.is_terminal:
            target = self.status
        elif present and proof:
            target = ReviewItemStatus.RESOLVED
        else:
            target = ReviewItemStatus.OPEN
        transition = ReviewItemTransition(
            from_status=self.status,
            to_status=target,
            commit_sha=commit_sha,
            explanation=explanation,
        )
        return ReviewItemLifecycle(
            item_id=self.item_id,
            status=target,
            first_seen_sha=self.first_seen_sha,
            last_audited_sha=commit_sha,
            status_explanation=explanation,
            transitions=self.transitions + (transition,),
        )

    def dismiss(
        self,
        commit_sha: str,
        explanation: str = "Dismissed by command",
    ) -> ReviewItemLifecycle:
        """Dismiss an active lifecycle and make dismissal terminal."""
        commit_sha = str(commit_sha)
        if self.status is ReviewItemStatus.DISMISSED:
            return self.audit(commit_sha, explanation=explanation)
        if self.status is ReviewItemStatus.RESOLVED:
            return self.audit(commit_sha, explanation=explanation)
        transition = ReviewItemTransition(
            from_status=self.status,
            to_status=ReviewItemStatus.DISMISSED,
            commit_sha=commit_sha,
            explanation=explanation,
        )
        return ReviewItemLifecycle(
            item_id=self.item_id,
            status=ReviewItemStatus.DISMISSED,
            first_seen_sha=self.first_seen_sha,
            last_audited_sha=commit_sha,
            status_explanation=explanation,
            transitions=self.transitions + (transition,),
        )
