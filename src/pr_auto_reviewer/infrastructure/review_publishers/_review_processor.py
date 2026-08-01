"""Shared processor that extracts review-publication logic from platform adapters.

Pulls verdict mapping, item filtering, body formatting, and COMMENT‑vs‑formal
decision into a single place so Forgejo and GitHub publishers only carry
platform‑specific API details.
"""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.review_publishers._shared import (
    _VERDICT_TO_EVENT,
    _body_formatter,
    ReasonBuilder,
)
from pr_auto_reviewer.infrastructure.review_publishers.review_publishing_service import (
    ReviewPublishingService,
)


@dataclass
class ProcessedReview:
    """Carrier for the output of the review‑publication processor.

    The verdict *event* is the platform‑agnostic mapping (e.g. ``"APPROVE"``).
    Platform‑specific overrides (e.g. Forgejo ``APPROVE → APPROVED``) are
    applied by the caller *after* processing.
    """

    verdict_event: str
    body: str
    blocking_items: list[ReviewItem]
    is_comment_only: bool
    non_blocking_body: str | None = None


class ReviewPublisherProcessor:
    """Processes a ``CodeReview`` into platform‑agnostic publication components.

    Absorbs verdict‑to‑event lookup, blocking/non‑blocking item filtering,
    reason construction, body formatting, and the COMMENT‑vs‑formal path
    decision so that every platform adapter that publishes a review reuses
    the same logic.

    Depends on ``ReviewPublishingService`` for the item‑count offset used by
    the body formatter and for the underlying HTTP calls made by the caller
    after processing.
    """

    def __init__(self, publishing_service: ReviewPublishingService) -> None:
        self._publishing = publishing_service

    def process(
        self, pr_id: PullRequestId, review: CodeReview,
    ) -> ProcessedReview:
        """Convert *review* into a ``ProcessedReview`` ready for platform dispatch."""
        verdict_event = _VERDICT_TO_EVENT.get(review.verdict, "COMMENT")

        if verdict_event == "COMMENT":
            return self._build_comment_path(pr_id, review)

        return self._build_formal_path(pr_id, review, verdict_event)

    def _build_comment_path(
        self, pr_id: PullRequestId, review: CodeReview,
    ) -> ProcessedReview:
        non_blocking = [i for i in review.items if not i.severity.is_blocking]
        comment_review = CodeReview(
            verdict=review.verdict,
            reason=ReasonBuilder.build(non_blocking),
            summary=review.summary,
            items=non_blocking,
            suggestions=review.suggestions,
            praise=review.praise,
            model_used=review.model_used,
        )
        body = _body_formatter.format(
            comment_review,
            start_number=self._publishing.count_existing_items(pr_id),
        )
        return ProcessedReview(
            verdict_event="COMMENT",
            body=body,
            blocking_items=[],
            is_comment_only=True,
        )

    def _build_formal_path(
        self, pr_id: PullRequestId, review: CodeReview, verdict_event: str,
    ) -> ProcessedReview:
        blocking = [i for i in review.items if i.severity.is_blocking]
        non_blocking = [i for i in review.items if not i.severity.is_blocking]
        body_review = CodeReview(
            verdict=review.verdict,
            reason=ReasonBuilder.build(blocking),
            summary=review.summary,
            items=blocking,
            suggestions=review.suggestions,
            praise=review.praise,
            model_used=review.model_used,
        )
        body = _body_formatter.format(
            body_review,
            start_number=self._publishing.count_existing_items(pr_id),
        )
        non_blocking_body: str | None = None
        if non_blocking:
            comment_review = CodeReview(
                verdict=ReviewVerdict.COMMENTED,
                reason=ReasonBuilder.build(non_blocking),
                summary="Non-blocking review items",
                items=non_blocking,
                suggestions=[],
                praise=[],
                model_used=review.model_used,
            )
            non_blocking_body = _body_formatter.format(
                comment_review,
                start_number=self._publishing.count_existing_items(pr_id) + len(blocking),
            )
        return ProcessedReview(
            verdict_event=verdict_event,
            body=body,
            blocking_items=blocking,
            is_comment_only=False,
            non_blocking_body=non_blocking_body,
        )
