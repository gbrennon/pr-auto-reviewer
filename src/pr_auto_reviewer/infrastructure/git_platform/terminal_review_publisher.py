"""TerminalReviewPublisherAdapter — prints review to stdout."""

from __future__ import annotations

import logging

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.git_platform.review_publisher import (
    format_review_body,
)

logger = logging.getLogger(__name__)


class TerminalReviewPublisherAdapter(ReviewPublisherPort):
    """Outputs a CodeReview to stdout instead of a remote platform."""

    def publish(self, pr_id: PullRequestId, review: CodeReview) -> None:
        body = format_review_body(review)
        logger.info(
            "Terminal output for PR %s: verdict=%s, items=%d",
            pr_id, review.verdict.value, len(review.items),
        )
        print(f"\n{'=' * 60}")
        print(f"  Review for {pr_id}")
        print(f"{'=' * 60}\n")
        print(body)
        print(f"\n{'=' * 60}\n")
