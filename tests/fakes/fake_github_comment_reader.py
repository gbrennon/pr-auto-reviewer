"""Fake GithubCommentReader for tests."""

from __future__ import annotations

from datetime import datetime, timezone

from pr_auto_reviewer.application.ports.outbound.comment_reader_port import (
    CommentReaderPort,
)
from pr_auto_reviewer.domain.value_objects.comment_id import CommentId
from pr_auto_reviewer.domain.value_objects.pr_comment import PrComment
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class FakeGithubCommentReader(CommentReaderPort):
    """Fake GithubCommentReader that returns pre-configured comments without making HTTP calls."""

    def __init__(self) -> None:
        self.get_comments_calls: list[tuple[PullRequestId]] = []

    def get_comments(self, pr_id: PullRequestId) -> list[PrComment]:
        """Return fake comments without making HTTP calls."""
        self.get_comments_calls.append((pr_id,))
        # Return pre-configured comments
        return [
            PrComment(
                id=CommentId("1"),
                body="Test comment 1",
                created_at=datetime.now(timezone.utc),
            ),
            PrComment(
                id=CommentId("2"),
                body="Test comment 2",
                created_at=datetime.now(timezone.utc),
            ),
        ]