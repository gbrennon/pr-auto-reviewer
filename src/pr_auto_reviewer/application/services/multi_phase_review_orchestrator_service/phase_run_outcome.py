"""_PhaseRunOutcome — result of one full phase sequence plus its refutation evidence."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.value_objects.code_review import CodeReview


@dataclass(frozen=True)
class _PhaseRunOutcome:
    """Result of one full phase sequence plus its refutation evidence.

    ``dropped_findings`` counts model-reported findings that did not
    survive verification (synthetic filters, verifier refutation).  A
    zero-item review with a positive count is a *correct* refutation,
    not an under-examined diff — it must never trigger feedback
    pressure to manufacture findings.
    """

    review: CodeReview
    dropped_findings: int = 0

    @property
    def is_clean_refutation(self) -> bool:
        """Return True if all reported findings were refuted during verification."""
        return not self.review.items and self.dropped_findings > 0

    @property
    def has_items(self) -> bool:
        """Return True if the review contains findings."""
        return bool(self.review.items)
