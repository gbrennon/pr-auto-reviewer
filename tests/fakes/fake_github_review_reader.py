from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.comment_reader_port import (
    CommentReaderPort,
)
from pr_auto_reviewer.domain.value_objects.pr_comment import PrComment
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class FakeGithubReviewReader(CommentReaderPort):
    """Fake GithubReviewReader that returns pre-configured comments without making HTTP calls."""

    def __init__(self) -> None:
        self.get_comments_calls: list[tuple[PullRequestId]] = []

    def get_comments(self, pr_id: PullRequestId) -> list[PrComment]:
        """Return fake comments without making HTTP calls."""
        self.get_comments_calls.append((pr_id,))
        return [
            PrComment(
                id="1",
                body="Test review comment",
                created_at="2024-01-01T00:00:00Z",
            ),
        ]