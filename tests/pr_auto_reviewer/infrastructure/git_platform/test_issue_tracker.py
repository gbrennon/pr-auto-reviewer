"""Tests for GitIssueTrackerAdapter using fixture data."""

import pytest

from pr_auto_reviewer.domain.exceptions.issue_creation_error import IssueCreationError
from pr_auto_reviewer.infrastructure.git_platform.issue_tracker import (
    GitIssueTrackerAdapter,
)


class TestGitIssueTrackerAdapter:
    """Tests for GitIssueTrackerAdapter using captured fixture data."""

    def test_create_returns_issue(self, patched_private_client):
        """Create returns Issue entity with correct data."""
        adapter = GitIssueTrackerAdapter(patched_private_client)
        issue = adapter.create("o/r", "Test Title", "Test Body")
        assert issue.id > 0
        assert issue.title == "Test Title"
        assert issue.body == "Test Body"

    def test_create_raises_on_error(self, patched_private_client, monkeypatch):
        """HTTP errors become IssueCreationError."""
        monkeypatch.setattr(
            patched_private_client, "post",
            lambda path, body: (_ for _ in ()).throw(Exception("500 Error"))
        )
        adapter = GitIssueTrackerAdapter(patched_private_client)
        with pytest.raises(IssueCreationError):
            adapter.create("o/r", "T", "B")

    def test_create_missing_number_field(self, patched_private_client, monkeypatch):
        """Handles response missing number field."""
        monkeypatch.setattr(patched_private_client, "post", lambda path, body: {"title": "x"})
        adapter = GitIssueTrackerAdapter(patched_private_client)
        issue = adapter.create("o/r", "t", "b")
        assert issue.id == 0

    def test_create_string_number_field(self, patched_private_client, monkeypatch):
        """Handles number field as string."""
        monkeypatch.setattr(patched_private_client, "post", lambda path, body: {"number": "42"})
        adapter = GitIssueTrackerAdapter(patched_private_client)
        issue = adapter.create("o/r", "t", "b")
        assert issue.id == 42
