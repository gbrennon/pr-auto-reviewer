"""Tests for ForgejoIssueTracker using fixture data."""

import pytest

from pr_auto_reviewer.domain.exceptions.issue_creation_error import IssueCreationError
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.forgejo.issue_tracker import (
    ForgejoIssueTracker,
)

_SOURCE_PR = PullRequestId(repository="o/r", number=42)


class TestForgejoIssueTracker:
    def test_create_returns_issue(self, patched_private_client):
        adapter = ForgejoIssueTracker(patched_private_client)

        issue = adapter.create(
            "o/r",
            "Test Title",
            "Test Body",
            source_pr_id=_SOURCE_PR,
            source_item_id="item-1",
        )

        assert issue.id > 0
        assert issue.title == "Test Title"
        assert issue.body == "Test Body"
        assert issue.source_pr_id == _SOURCE_PR
        assert issue.source_item_id == "item-1"

    def test_create_raises_on_error(self, patched_private_client, monkeypatch):
        def fail_post(path, body, *, repo=None):
            raise Exception("500 Error")

        monkeypatch.setattr(patched_private_client, "post", fail_post)
        adapter = ForgejoIssueTracker(patched_private_client)

        with pytest.raises(IssueCreationError):
            adapter.create(
                "o/r",
                "T",
                "B",
                source_pr_id=_SOURCE_PR,
                source_item_id="item-1",
            )

    @pytest.mark.parametrize("number", (None, "42", 0, -1, True))
    def test_create_rejects_non_positive_integer_number(
        self, patched_private_client, monkeypatch, number
    ):
        def return_number(path, body, *, repo=None):
            return {"number": number}

        monkeypatch.setattr(patched_private_client, "post", return_number)
        adapter = ForgejoIssueTracker(patched_private_client)

        with pytest.raises(IssueCreationError):
            adapter.create(
                "o/r",
                "t",
                "b",
                source_pr_id=_SOURCE_PR,
                source_item_id="item-1",
            )
