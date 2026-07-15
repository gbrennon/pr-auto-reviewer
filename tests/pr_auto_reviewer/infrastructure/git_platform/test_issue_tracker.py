"""Tests for ForgejoIssueTracker using fixture data."""

import pytest

from pr_auto_reviewer.domain.exceptions.issue_creation_error import IssueCreationError
from pr_auto_reviewer.infrastructure.forgejo.issue_tracker import (
    ForgejoIssueTracker,
)

class TestForgejoIssueTracker:
    """Tests for ForgejoIssueTracker using captured fixture data."""

    def test_create_returns_issue(self, patched_private_client):
        """Create returns Issue entity with correct data."""
        adapter = ForgejoIssueTracker(patched_private_client)
        issue = adapter.create("o/r", "Test Title", "Test Body")
        assert issue.id > 0
        assert issue.title == "Test Title"
        assert issue.body == "Test Body"

    def test_create_raises_on_error(self, patched_private_client, monkeypatch):
        """HTTP errors become IssueCreationError."""
        monkeypatch.setattr(
            patched_private_client, "post",
            lambda path, body, *, repo=None: (_ for _ in ()).throw(Exception("500 Error"))
        )
        adapter = ForgejoIssueTracker(patched_private_client)
        with pytest.raises(IssueCreationError):
            adapter.create("o/r", "T", "B")

    def test_create_missing_number_field(self, patched_private_client, monkeypatch):
        """Handles response missing number field."""
        monkeypatch.setattr(patched_private_client, "post", lambda path, body, *, repo=None: {"title": "x"})
        adapter = ForgejoIssueTracker(patched_private_client)
        issue = adapter.create("o/r", "t", "b")
        assert issue.id == 0

    def test_create_string_number_field(self, patched_private_client, monkeypatch):
        """Handles number field as string."""
        monkeypatch.setattr(patched_private_client, "post", lambda path, body, *, repo=None: {"number": "42"})
        adapter = ForgejoIssueTracker(patched_private_client)
        issue = adapter.create("o/r", "t", "b")
        assert issue.id == 42
