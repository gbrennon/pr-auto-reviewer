"""Fake ForgejoReviewPublisher for tests."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class FakeForgejoReviewPublisher:
    """Fake ForgejoReviewPublisher that tracks review publication without making HTTP calls."""

    def __init__(self) -> None:
        self.publish_calls: list[tuple[str, CodeReview, bool]] = []

    def publish(self, review: CodeReview, official: bool = True) -> str:
        """Track publish call without making HTTP call."""
        self.publish_calls.append((review.verdict, review, official))
        # Return a fake event string
        return f"{review.verdict.lower()}_event"