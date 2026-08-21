from __future__ import annotations

import pytest

from tests.fakes.fake_github_review_reader import FakeGithubReviewReader
from pr_auto_reviewer.domain.value_objects.pr_comment import PrComment
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class TestFakeGithubReviewReader:
    """Tests using the fake GithubReviewReader."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake review reader can be instantiated."""
        fake = FakeGithubReviewReader()
        assert fake is not None

    def test_fake_get_comments(self) -> None:
        """Fake get_comments returns configured comments."""
        fake = FakeGithubReviewReader()
        pr_id = PullRequestId(repository="owner/repo", number=1)
        comments = fake.get_comments(pr_id)
        assert len(comments) == 1
        assert fake.get_comments_calls == [(pr_id,)]
        assert comments[0].body == "Test review comment"