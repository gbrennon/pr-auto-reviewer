"""Fake GithubCommentPublisher for tests."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.comment_publisher_port import (
    CommentPublisherPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class FakeGithubCommentPublisher(CommentPublisherPort):
    """Fake GithubCommentPublisher that tracks POST calls without making HTTP calls."""

    def __init__(self) -> None:
        self.post_calls: list[tuple[PullRequestId, str]] = []
        self.post_errors: list[tuple[PullRequestId, str]] = []

    def post(self, pr_id: PullRequestId, body: str) -> None:
        """Track POST call without making HTTP call."""
        self.post_calls.append((pr_id, body))

    def simulate_error(self, pr_id: PullRequestId, body: str) -> None:
        """Simulate a POST error for testing error handling."""
        self.post_errors.append((pr_id, body))