from __future__ import annotations

import logging

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyFormatter,
)
from pr_auto_reviewer.infrastructure.review_publishers.review_publishing_service import (
    ReviewPublishingService,
)

logger = logging.getLogger(__name__)

_VERDICT_TO_EVENT: dict[ReviewVerdict, str] = {
    ReviewVerdict.APPROVED: "APPROVE",
    ReviewVerdict.CHANGES_REQUESTED: "REQUEST_CHANGES",
    ReviewVerdict.COMMENTED: "COMMENT",
}

_body_formatter = ReviewBodyFormatter()


class ForgejoReviewPublisher(ReviewPublisherPort):
    """Publishes a ``CodeReview`` as a Forgejo/Codeberg PR review."""

    def __init__(
        self,
        client: GitPlatformHttpClient,
        reviewer_token: str,
        reviewer_username: str,
        owner_client: GitPlatformHttpClient,
    ) -> None:
        self._publishing = ReviewPublishingService(
            client, reviewer_username, owner_client,
        )

    def publish(self, pr_id: PullRequestId, review: CodeReview) -> None:
        self._publishing.verify_tokens(pr_id)

        verdict_event = _VERDICT_TO_EVENT.get(review.verdict, "COMMENT")

        if verdict_event == "APPROVE":
            verdict_event = "APPROVED"

        logger.info(
            "Publishing review for PR %s: verdict=%s, event=%s, "
            "items_count=%d, summary_len=%d",
            pr_id,
            review.verdict.value,
            verdict_event,
            len(review.items),
            len(review.summary) if review.summary else 0,
        )

        if verdict_event == "COMMENT":
            non_blocking_items = [i for i in review.items if not i.severity.is_blocking]
            comment_review = CodeReview(
                verdict=review.verdict,
                reason=review.reason,
                summary=review.summary,
                items=non_blocking_items,
                suggestions=review.suggestions,
                praise=review.praise,
                model_used=review.model_used,
            )
            comment_body = _body_formatter.format(
                comment_review,
                start_number=self._publishing.count_existing_items(pr_id),
            )
            self._publishing.publish_comment(pr_id, comment_body)
            return

        blocking = [i for i in review.items if i.severity.is_blocking]
        non_blocking_items = [i for i in review.items if not i.severity.is_blocking]
        body_review = CodeReview(
            verdict=review.verdict,
            reason=review.reason,
            summary=review.summary,
            items=non_blocking_items,
            suggestions=review.suggestions,
            praise=review.praise,
            model_used=review.model_used,
        )
        body = _body_formatter.format(
            body_review,
            start_number=self._publishing.count_existing_items(pr_id),
        )

        self._publishing.request_reviewer(pr_id)
        self._publishing.publish_formal_review(
            pr_id,
            verdict_event,
            body,
            blocking,
            official=True,
            diff_headers=None,
        )
