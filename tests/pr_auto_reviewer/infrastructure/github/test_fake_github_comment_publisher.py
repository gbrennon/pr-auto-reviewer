"""Tests for GithubCommentPublisher using fake."""

from __future__ import annotations

import pytest

from tests.fakes.fake_github_comment_publisher import FakeGithubCommentPublisher
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class TestFakeGithubCommentPublisher:
    """Tests using the fake GithubCommentPublisher."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake comment publisher can be instantiated."""
        fake = FakeGithubCommentPublisher()
        assert fake is not None

    def test_fake_post_success(self) -> None:
        """Fake post tracks successful calls."""
        fake = FakeGithubCommentPublisher()
        pr_id = PullRequestId(repository="owner/repo", number=1)
        fake.post(pr_id, "Test comment body")
        assert len(fake.post_calls) == 1
        assert fake.post_calls[0] == (pr_id, "Test comment body")

    def test_fake_post_error_simulation(self) -> None:
        """Fake post can simulate errors."""
        fake = FakeGithubCommentPublisher()
        pr_id = PullRequestId(repository="owner/repo", number=1)
        fake.simulate_error(pr_id, "Test comment body")
        assert len(fake.post_errors) == 1