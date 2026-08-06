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
from pr_auto_reviewer.infrastructure.review_publishers._review_processor import (
    ReviewPublisherProcessor,
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
        self._processor = ReviewPublisherProcessor(self._publishing)

    def publish(self, pr_id: PullRequestId, review: CodeReview, diff: PullRequestDiff | None = None) -> None:
        self._publishing.verify_tokens(pr_id)

        processed = self._processor.process(pr_id, review)

        logger.info(
            "Publishing review for PR %s: verdict=%s, event=%s, "
            "items_count=%d, summary_len=%d, mode=%s",
            pr_id,
            review.verdict.value,
            processed.verdict_event,
            len(review.items),
            len(review.summary) if review.summary else 0,
            self._review_mode,
        )

        if processed.is_comment_only:
            self._publishing.publish_comment(pr_id, processed.body)
            return

        self._publishing.publish_formal_review(
            pr_id,
            processed.verdict_event,
            processed.body,
            processed.blocking_items,
            platform="github",
            official=False,
            diff_headers={"Accept": "application/vnd.github.diff"},
            diff=diff,
        )

