"""Processor that extracts review-publication logic from platform adapters.

Pulls verdict mapping, item filtering, body formatting, and the
COMMENT-vs-formal decision into a single place so Forgejo and GitHub
publishers only carry platform-specific API details.
"""

from dataclasses import dataclass

from pr_auto_reviewer.application.ports.outbound.verdict_event_mapper_port import (
    VerdictEventMapperPort,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyRenderer,
)
from pr_auto_reviewer.infrastructure.review_publishers.reason_factory import (
    ReasonFactory,
)


@dataclass
class ProcessedReview:
    """Carrier for the output of the review-publication processor.

    The verdict *event* is the platform-specific mapping produced by the
    injected ``VerdictEventMapperPort`` (e.g. GitHub ``APPROVE``, Forgejo
    ``APPROVED``). No post-processing is applied by the caller.
    """

    verdict_event: str
    body: str
    blocking_items: list[ReviewItem]
    is_comment_only: bool


class ReviewPublisherProcessor:
    """Processes a ``CodeReview`` into platform-agnostic publication components.

    Absorbs verdict-to-event lookup, blocking/non-blocking item filtering,
    reason construction, body formatting, and the COMMENT-vs-formal path
    decision so that every platform adapter that publishes a review reuses
    the same logic.
    """

    def __init__(
        self,
        body_renderer: ReviewBodyRenderer,
        verdict_mapper: VerdictEventMapperPort,
    ) -> None:
        self._body_renderer = body_renderer
        self._verdict_mapper = verdict_mapper
        self._reason_factory = ReasonFactory()

    def process(
        self, pr_id: PullRequestId, review: CodeReview,
    ) -> ProcessedReview:
        """Convert *review* into a ``ProcessedReview`` ready for platform dispatch."""
        verdict_event = self._verdict_mapper.map(review.verdict)

        if verdict_event == "COMMENT":
            return self._build_comment_path(pr_id, review)

        return self._build_formal_path(pr_id, review, verdict_event)

    def _build_comment_path(
        self, pr_id: PullRequestId, review: CodeReview,
    ) -> ProcessedReview:
        non_blocking = [i for i in review.items if not i.is_blocking]
        comment_review = CodeReview(
            verdict=ReviewVerdict.COMMENTED,
            reason=self._reason_factory.make(non_blocking),
            summary=review.summary,
            items=non_blocking,
            suggestions=review.suggestions,
            praise=review.praise,
            model_used=review.model_used,
        )
        body = self._body_renderer.render(comment_review)
        return ProcessedReview(
            verdict_event="COMMENT",
            body=body,
            blocking_items=[],
            is_comment_only=True,
        )

    def _build_formal_path(
        self, pr_id: PullRequestId, review: CodeReview, verdict_event: str,
    ) -> ProcessedReview:
        all_items = list(review.items)
        body_review = CodeReview(
            verdict=review.verdict,
            reason=self._reason_factory.make(all_items),
            summary=review.summary,
            items=all_items,
            suggestions=review.suggestions,
            praise=review.praise,
            model_used=review.model_used,
        )
        body = self._body_renderer.render(body_review)
        return ProcessedReview(
            verdict_event=verdict_event,
            body=body,
            blocking_items=all_items,
            is_comment_only=False,
        )