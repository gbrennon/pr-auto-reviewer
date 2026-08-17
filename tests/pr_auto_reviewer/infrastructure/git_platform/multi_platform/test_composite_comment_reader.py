"""Tests for CompositeCommentReader using stub port implementations."""

from datetime import UTC, datetime

import pytest

from pr_auto_reviewer.application.ports.outbound.comment_reader_port import (
    CommentReaderPort,
)
from pr_auto_reviewer.domain.value_objects.comment_id import CommentId
from pr_auto_reviewer.domain.value_objects.pr_comment import PrComment
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_comment_reader import (
    CompositeCommentReader,
)

_TS = datetime(2025, 1, 15, tzinfo=UTC)


class _StubCommentReader(CommentReaderPort):
    """Stub reader that records calls and returns canned comments."""

    def __init__(self, comments: list[PrComment] | None = None) -> None:
        self.get_comments_calls: list[PullRequestId] = []
        self._comments = comments or []

    def get_comments(self, pr_id: PullRequestId) -> list[PrComment]:
        self.get_comments_calls.append(pr_id)
        return self._comments


class TestCompositeCommentReader:
    def test_get_comments_routes_to_correct_platform(self):
        github_comment = PrComment(
            id=CommentId("gh-1"), body="github comment", created_at=_TS,
        )
        forgejo_comment = PrComment(
            id=CommentId("fj-1"), body="forgejo comment", created_at=_TS,
        )
        github_reader = _StubCommentReader([github_comment])
        forgejo_reader = _StubCommentReader([forgejo_comment])
        composite = CompositeCommentReader({
            "github": github_reader,
            "forgejo": forgejo_reader,
        })

        gh_result = composite.get_comments(
            PullRequestId(repository="github:owner/repo", number=1)
        )
        fj_result = composite.get_comments(
            PullRequestId(repository="codeberg:org/proj", number=2)
        )

        assert len(gh_result) == 1
        assert gh_result[0].body == "github comment"
        assert len(fj_result) == 1
        assert fj_result[0].body == "forgejo comment"
        assert len(github_reader.get_comments_calls) == 1
        assert github_reader.get_comments_calls[0].repository == "owner/repo"
        assert len(forgejo_reader.get_comments_calls) == 1
        assert forgejo_reader.get_comments_calls[0].repository == "org/proj"

    def test_get_comments_defaults_to_forgejo_without_prefix(self):
        forgejo_comment = PrComment(
            id=CommentId("fj-1"), body="forgejo comment", created_at=_TS,
        )
        forgejo_reader = _StubCommentReader([forgejo_comment])
        composite = CompositeCommentReader({"forgejo": forgejo_reader})

        result = composite.get_comments(
            PullRequestId(repository="owner/repo", number=1)
        )

        assert len(result) == 1
        assert result[0].body == "forgejo comment"
        assert len(forgejo_reader.get_comments_calls) == 1
        assert forgejo_reader.get_comments_calls[0].repository == "owner/repo"

    def test_get_comments_raises_for_unknown_platform(self):
        composite = CompositeCommentReader({})

        with pytest.raises(ValueError, match="No comment reader for platform"):
            composite.get_comments(
                PullRequestId(repository="unknown:owner/repo", number=1)
            )
