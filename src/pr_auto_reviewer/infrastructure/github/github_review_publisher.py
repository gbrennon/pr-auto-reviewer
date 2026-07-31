from __future__ import annotations

import logging

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_diff import (
    PullRequestDiff,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.review_publishers._shared import (
    _VERDICT_TO_EVENT,
    _body_formatter,
    ReasonBuilder,
)
from pr_auto_reviewer.infrastructure.review_publishers.review_publishing_service import (
    ReviewPublishingService,
)
logger = logging.getLogger(__name__)


class GithubReviewPublisher(ReviewPublisherPort):
    """Publishes a ``CodeReview`` as a GitHub PR review."""

    def __init__(
        self,
        client: GitPlatformHttpClient,
        owner_client: GitPlatformHttpClient,
        review_mode: str = "formal",
    ) -> None:
        self._review_mode = review_mode
        self._publishing = ReviewPublishingService(client, owner_client)

    def publish(self, pr_id: PullRequestId, review: CodeReview, diff: PullRequestDiff | None = None) -> None:
        self._publishing.verify_tokens(pr_id)

        verdict_event = _VERDICT_TO_EVENT.get(review.verdict, "COMMENT")

        logger.info(
            "Publishing review for PR %s: verdict=%s, event=%s, "
            "items_count=%d, summary_len=%d, mode=%s",
            pr_id,
            review.verdict.value,
            verdict_event,
            len(review.items),
            len(review.summary) if review.summary else 0,
            self._review_mode,
        )

        if verdict_event == "COMMENT":
            non_blocking_items = [i for i in review.items if not i.severity.is_blocking]
            comment_review = CodeReview(
                verdict=review.verdict,
                reason=ReasonBuilder.build(non_blocking_items),
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
            reason=ReasonBuilder.build(non_blocking_items),
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


        self._publishing.publish_formal_review(
            pr_id,
            verdict_event,
            body,
            blocking,
            platform="github",
            official=False,
            diff_headers={"Accept": "application/vnd.github.diff"},
            diff=diff,
        )
