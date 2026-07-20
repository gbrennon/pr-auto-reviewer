"""Fixtures for composite delegation — real port implementations for testing."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.changeset_fetcher_port import (
    ChangesetFetcherPort,
)
from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class RecordingReviewPublisher(ReviewPublisherPort):
    """Real ReviewPublisherPort implementation that records calls for test assertions."""

    def __init__(self) -> None:
        self.publish_calls: list[tuple[PullRequestId, CodeReview, PullRequestDiff | None]] = []

    def publish(self, pr_id: PullRequestId, review: CodeReview, diff: PullRequestDiff | None = None) -> None:
        self.publish_calls.append((pr_id, review, diff))


class RecordingChangesetFetcher(ChangesetFetcherPort):
    """Real ChangesetFetcherPort implementation that records calls for test assertions."""

    def __init__(self, diff_content: str = "mock diff content") -> None:
        self.fetch_calls: list[tuple[PullRequestId, CommitSha]] = []
        self._diff_content = diff_content

    def fetch(self, pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff:
        self.fetch_calls.append((pr_id, sha))
        return PullRequestDiff(
            pr_id=pr_id,
            head_sha=sha,
            diff_content=self._diff_content,
        )


class FailingChangesetFetcher(ChangesetFetcherPort):
    """Real ChangesetFetcherPort that always raises — for error path testing."""

    def fetch(self, pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff:
        raise ValueError("simulated fetch failure")
