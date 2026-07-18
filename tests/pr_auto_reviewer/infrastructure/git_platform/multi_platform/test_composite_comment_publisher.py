"""Tests for CompositeCommentPublisher using stub port implementations."""

import pytest

from pr_auto_reviewer.application.ports.outbound.comment_publisher_port import (
    CommentPublisherPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_comment_publisher import (
    CompositeCommentPublisher,
)


class _StubCommentPublisher(CommentPublisherPort):
    """Stub publisher that records calls for test assertion."""

    def __init__(self) -> None:
        self.post_calls: list[tuple[PullRequestId, str]] = []

    def post(self, pr_id: PullRequestId, body: str) -> None:
        self.post_calls.append((pr_id, body))


class TestCompositeCommentPublisher:
    def test_post_routes_to_correct_platform(self):
        github_publisher = _StubCommentPublisher()
        forgejo_publisher = _StubCommentPublisher()
        composite = CompositeCommentPublisher({
            "github": github_publisher,
            "forgejo": forgejo_publisher,
        })

        composite.post(
            PullRequestId(repository="github:owner/repo", number=1),
            "github comment body",
        )
        composite.post(
            PullRequestId(repository="codeberg:org/proj", number=2),
            "forgejo comment body",
        )

        assert len(github_publisher.post_calls) == 1
        assert github_publisher.post_calls[0][0].repository == "owner/repo"
        assert github_publisher.post_calls[0][0].number == 1
        assert github_publisher.post_calls[0][1] == "github comment body"

        assert len(forgejo_publisher.post_calls) == 1
        assert forgejo_publisher.post_calls[0][0].repository == "org/proj"
        assert forgejo_publisher.post_calls[0][0].number == 2
        assert forgejo_publisher.post_calls[0][1] == "forgejo comment body"

    def test_post_defaults_to_forgejo_without_prefix(self):
        forgejo_publisher = _StubCommentPublisher()
        composite = CompositeCommentPublisher({"forgejo": forgejo_publisher})

        composite.post(
            PullRequestId(repository="owner/repo", number=1),
            "body",
        )

        assert len(forgejo_publisher.post_calls) == 1
        assert forgejo_publisher.post_calls[0][0].repository == "owner/repo"

    def test_post_raises_for_unknown_platform(self):
        composite = CompositeCommentPublisher({})

        with pytest.raises(ValueError, match="No comment publisher for platform"):
            composite.post(
                PullRequestId(repository="unknown:owner/repo", number=1),
                "body",
            )
