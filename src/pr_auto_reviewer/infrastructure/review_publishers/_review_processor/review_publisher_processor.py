from ._shared import *
from .processed_review import ProcessedReview


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

    @classmethod
    def _active_blocking(
        cls, items: list[ReviewItem],
    ) -> list[ReviewItem]:
        return [item for item in cls._active_items(items) if item.is_blocking]

    @classmethod
    def _active_non_blocking(
        cls, items: list[ReviewItem],
    ) -> list[ReviewItem]:
        return [
            item for item in cls._active_items(items) if not item.is_blocking
        ]

    @staticmethod
    def _active_items(items: list[ReviewItem]) -> list[ReviewItem]:
        return [item for item in items if item.is_active]

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
        non_blocking = self._active_non_blocking(review.items)
        suggestions = self._active_items(review.suggestions)
        comment_review = CodeReview(
            verdict=review.verdict,
            reason=review.reason or self._reason_factory.make(non_blocking),
            summary=review.summary,
            items=non_blocking,
            suggestions=suggestions,
            praise=review.praise,
            model_used=review.model_used,
        )
        body = self._body_renderer.render(
            comment_review,
            audit_records=self._audit_records(review),
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
        blocking_items = self._active_blocking(review.items)
        non_blocking = self._active_non_blocking(review.items)
        suggestions = self._active_items(review.suggestions)
        body_review = CodeReview(
            verdict=review.verdict,
            reason=review.reason or self._reason_factory.make(blocking_items),
            summary=review.summary,
            items=blocking_items,
            praise=review.praise,
            model_used=review.model_used,
        )
        body = self._body_renderer.render(
            body_review,
            audit_records=self._audit_records(review),
        )
        comment_body = self._render_non_blocking_comment(
            review, non_blocking, suggestions,
        )
        return ProcessedReview(
            verdict_event=verdict_event,
            body=body,
            blocking_items=blocking_items,
            is_comment_only=False,
            comment_body=comment_body,
        )

    def _render_non_blocking_comment(
        self,
        review: CodeReview,
        items: list[ReviewItem],
        suggestions: list[ReviewItem],
    ) -> str | None:
        if not items and not suggestions:
            return None
        comment_review = CodeReview(
            verdict=review.verdict,
            reason=review.reason or self._reason_factory.make(items),
            summary=review.summary,
            items=items,
            suggestions=suggestions,
            model_used=review.model_used,
        )
        return self._body_renderer.render(comment_review)

    @classmethod
    def _audit_records(cls, review: CodeReview) -> list[ReviewItem]:
        """Return historical records suitable for the remediation section."""
        return [
            item
            for item in [*review.items, *review.suggestions]
            if item.status in {ReviewItemStatus.OPEN, ReviewItemStatus.RESOLVED}
            and item.status_explanation
        ]
