"""Tests for GithubPrLister using fake."""

from __future__ import annotations

import pytest

from tests.fakes.fake_github_pr_lister import FakeGithubPrLister
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.ports import OpenPullRequest


class TestFakeGithubPrLister:
    """Tests using the fake GithubPrLister."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake pr lister can be instantiated."""
        fake = FakeGithubPrLister()
        assert fake is not None

    def test_fake_list_open(self) -> None:
        """Fake list_open returns configured PRs."""
        fake = FakeGithubPrLister()
        prs = fake.list_open("owner/repo")
        assert len(prs) == 2
        assert fake.list_open_calls == ["owner/repo"]

    def test_fake_get_pr(self) -> None:
        """Fake get_pr returns PR by number."""
        fake = FakeGithubPrLister()
        pr = fake.get_pr("owner/repo", 1)
        assert pr is not None
        assert pr.pr_id.number == 1
        assert fake.get_pr_calls == [("owner/repo", 1)]

    def test_fake_get_pr_not_found(self) -> None:
        """Fake get_pr returns None for non-existent PR."""
        fake = FakeGithubPrLister()
        pr = fake.get_pr("owner/repo", 999)
        assert pr is None

    def test_fake_list_open_error(self) -> None:
        """Fake list_open can simulate an error."""
        fake = FakeGithubPrLister()
        try:
            fake.simulate_error_list_open()
            assert False, "Should have raised an exception"
        except Exception as e:
            assert "Simulated Forgejo API error" in str(e)