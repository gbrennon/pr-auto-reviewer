"""CodeReview — the complete, structured output produced by the LLM for a given diff."""

from dataclasses import dataclass, field

from ..entities.review_item import ReviewItem
from ..exceptions.review_verdict_error import ReviewVerdictError
from .review_verdict import ReviewVerdict
from .suggestion_origin import SuggestionOrigin


@dataclass(frozen=True)
class CodeReview:
    """The complete, structured output produced by the LLM for a given diff.

    A review is the *result* of running a model over a diff. It never mutates.
    A new commit means a new review, not an updated one.

    Every field must carry the review's real outcome. Default or
    placeholder values — a COMMENTED verdict, an empty reason or summary,
    or an unknown model — mean the review pipeline failed, and raise
    ``ReviewVerdictError`` instead of silently publishing a hollow
    result.
    """

    verdict: ReviewVerdict
    reason: str
    summary: str
    items: list[ReviewItem] = field(default_factory=list)
    suggestions: list[ReviewItem] = field(default_factory=list)
    praise: list[ReviewItem] = field(default_factory=list)
    model_used: str = ""
    suggestion_origin: SuggestionOrigin = SuggestionOrigin.ARCHITECTURE

    def __post_init__(self) -> None:
        """Reject default or unverified review outcomes."""
        if self.verdict is ReviewVerdict.COMMENTED:
            raise ReviewVerdictError(
                "CodeReview must carry an explicit APPROVED or "
                "CHANGES_REQUESTED verdict; COMMENTED is a pipeline "
                "failure, not a review outcome."
            )
        if not self.reason or not self.summary:
            raise ReviewVerdictError(
                "CodeReview must carry a non-empty reason and summary; "
                "empty values mean the review was not completed."
            )
        if not self.model_used:
            raise ReviewVerdictError(
                "CodeReview must name the model that produced it; an "
                "unknown model means the review did not run."
            )
