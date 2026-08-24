"""ReviewVerdictError — a review was constructed with a default/unauthoritative outcome."""

from pr_auto_reviewer.domain.exceptions.domain_error import DomainError


class ReviewVerdictError(DomainError):
    """Raised when a CodeReview carries a default or unverified outcome.

    The application automates PR interaction and must never publish a
    review that fell back to default values: a COMMENTED verdict, an
    empty reason or summary, or an unknown model name all mean the
    review pipeline failed to produce a real result. Every published
    review must carry an explicit APPROVED or CHANGES_REQUESTED verdict
    with the evidence behind it.
    """