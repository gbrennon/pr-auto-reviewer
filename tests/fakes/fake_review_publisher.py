"""Fake review publisher for tests."""

from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class FakeReviewPublisher:
    def __init__(self) -> None:
        self.publish_calls: list[tuple[PullRequestId, CodeReview, PullRequestDiff | None]] = []

    def publish(self, pr_id: PullRequestId, review: CodeReview, diff: PullRequestDiff | None = None) -> None:
        self.publish_calls.append((pr_id, review, diff))