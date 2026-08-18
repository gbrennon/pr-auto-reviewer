"""Behavioral tests for GithubCommentPublisher."""

import requests

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.github.comment_publisher import (
    GithubCommentPublisher,
)
from tests.fakes import FakeGitPlatformHttpClient


class TestGithubCommentPublisher:
    """Exercises GithubCommentPublisher against a fake GitPlatformHttpClient."""

    def test_post_when_success_then_does_not_raise(self) -> None:
        """A successful POST is logged and swallowed."""
        publisher = GithubCommentPublisher(
            FakeGitPlatformHttpClient(
                {"/repos/o/r/issues/3/comments": {"id": 1}}
            )
        )

        publisher.post(PullRequestId(repository="o/r", number=3), "hello")

    def test_post_when_request_fails_then_logs_and_does_not_raise(self) -> None:
        """A network failure is non-fatal: logged, not propagated."""
        publisher = GithubCommentPublisher(
            FakeGitPlatformHttpClient(
                {
                    "/repos/o/r/issues/3/comments": requests.RequestException(
                        "down"
                    )
                }
            )
        )

        publisher.post(PullRequestId(repository="o/r", number=3), "hello")