"""Tests for GithubRepoLister using fake."""

from __future__ import annotations

import pytest

from tests.fakes.fake_github_repo_lister import FakeGithubRepoLister
from pr_auto_reviewer.presentation.ports import RepoInfo


class TestFakeGithubRepoLister:
    """Tests using the fake GithubRepoLister."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake repo lister can be instantiated."""
        fake = FakeGithubRepoLister()
        assert fake is not None

    def test_fake_list_repos(self) -> None:
        """Fake list_repos returns configured repos."""
        fake = FakeGithubRepoLister()
        repos = fake.list_repos("gbrennon")
        assert len(repos) == 1
        assert fake.list_repos_calls == ["gbrennon"]

    def test_fake_get_repo(self) -> None:
        """Fake get_repo returns configured repo."""
        fake = FakeGithubRepoLister()
        repo = fake.get_repo("owner/test-repo")
        assert repo is not None
        assert fake.get_repo_calls == [("owner/test-repo", "main")]

    def test_fake_get_repo_not_found(self) -> None:
        """Fake get_repo returns None for non-existent repo."""
        fake = FakeGithubRepoLister()
        repo = fake.get_repo("nonexistent/repo")
        assert repo is None

    def test_fake_list_repos_error(self) -> None:
        """Fake list_repos can simulate an error."""
        fake = FakeGithubRepoLister()
        try:
            fake.simulate_error_list_repos()
            assert False, "Should have raised an exception"
        except Exception as e:
            assert "Simulated GitHub API error" in str(e)