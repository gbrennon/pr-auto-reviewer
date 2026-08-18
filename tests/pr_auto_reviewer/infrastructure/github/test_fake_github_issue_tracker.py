"""Tests for GithubIssueTracker using fake."""

from __future__ import annotations

import pytest

from tests.fakes.fake_github_issue_tracker import FakeGithubIssueTracker
from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class TestFakeGithubIssueTracker:
    """Tests using the fake GithubIssueTracker."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake issue tracker can be instantiated."""
        fake = FakeGithubIssueTracker()
        assert fake is not None

    def test_fake_create_success(self) -> None:
        """Fake create tracks successful calls."""
        fake = FakeGithubIssueTracker()
        issue = fake.create("owner/repo", "Test Title", "Test Body")
        assert len(fake.create_calls) == 1
        assert fake.create_calls[0] == ("owner/repo", "Test Title", "Test Body", "")
        assert isinstance(issue, Issue)

    def test_fake_create_error_simulation(self) -> None:
        """Fake create can simulate errors."""
        fake = FakeGithubIssueTracker()
        try:
            fake.simulate_error("owner/repo", "Test Title", "Test Body")
            assert False, "Should have raised an exception"
        except Exception as e:
            assert "Simulated API error" in str(e)