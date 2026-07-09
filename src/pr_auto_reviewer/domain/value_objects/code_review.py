"""CodeReview — the complete, structured output produced by the LLM for a given diff."""

from dataclasses import dataclass, field

from .review_verdict import ReviewVerdict
from ..entities.review_item import ReviewItem
from ..entities.review_suggestion import ReviewSuggestion
from ..entities.review_praise import ReviewPraise

@dataclass(frozen=True)
class CodeReview:
    """The complete, structured output produced by the LLM for a given diff.

    A review is the *result* of running a model over a diff. It never mutates.
    A new commit means a new review, not an updated one.
    """

    verdict: ReviewVerdict
    reason: str = ""
    summary: str = ""
    items: list[ReviewItem] = field(default_factory=list)
    suggestions: list[ReviewSuggestion] = field(default_factory=list)
    praise: list[ReviewPraise] = field(default_factory=list)
    model_used: str = ""
