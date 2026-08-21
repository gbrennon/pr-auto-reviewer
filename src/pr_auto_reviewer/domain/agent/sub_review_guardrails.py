"""SubReviewGuardrails — verdict-from-findings policy for a review phase sub-review."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


@dataclass(frozen=True)
class SubReviewGuardrails:
    """Guardrail policy keeping a sub-review verdict coherent with its findings.

    Uses the item blocking threshold to derive and validate the verdict a
    phase should publish: an approval never coexists with a blocking finding
    and a change request is never issued when nothing blocks the merge.
    """

    def verdict_for(
        self, items: list[ReviewItem]
    ) -> ReviewVerdict:
        """Return the verdict implied by the blocking status of *items*."""
        if not items:
            return ReviewVerdict.APPROVED
        if any(item.is_blocking for item in items):
            return ReviewVerdict.CHANGES_REQUESTED
        return ReviewVerdict.APPROVED

    def is_coherent(
        self, verdict: ReviewVerdict, items: list[ReviewItem]
    ) -> bool:
        """Return whether *verdict* is coherent with the items' blocking status."""
        has_blocking = any(item.is_blocking for item in items)
        incoherent = (
            (verdict is ReviewVerdict.APPROVED and has_blocking)
            or (
                verdict is ReviewVerdict.CHANGES_REQUESTED
                and not has_blocking
            )
        )
        return not incoherent

    def reconcile(
        self, verdict: ReviewVerdict, items: list[ReviewItem]
    ) -> ReviewVerdict:
        """Return a verdict coherent with *items*, preserving *verdict* when possible."""
        if self.is_coherent(verdict, items):
            return verdict
        return self.verdict_for(items)
