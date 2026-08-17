"""Tests for OpenPullRequest DTO."""

import pytest

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.ports.open_pull_request import OpenPullRequest


class TestOpenPullRequest:
    """Tests for OpenPullRequest dataclass."""

    def test_creation(self) -> None:
        """Creates OpenPullRequest with all fields."""
        pr_id = PullRequestId(repository="owner/repo", number=123)
        sha = CommitSha("abc123")
        pr = OpenPullRequest(
            pr_id=pr_id,
            head_sha=sha,
            title="Fix bug",
            is_draft=False,
        )

        assert pr.pr_id == pr_id
        assert pr.head_sha == sha
        assert pr.title == "Fix bug"
        assert pr.is_draft is False

    def test_is_draft_true(self) -> None:
        """Creates OpenPullRequest for draft PR."""
        pr_id = PullRequestId(repository="owner/repo", number=456)
        sha = CommitSha("def456")
        pr = OpenPullRequest(
            pr_id=pr_id,
            head_sha=sha,
            title="WIP feature",
            is_draft=True,
        )

        assert pr.is_draft is True

    def test_is_immutable(self) -> None:
        """OpenPullRequest is immutable (frozen=True)."""
        pr_id = PullRequestId(repository="owner/repo", number=789)
        sha = CommitSha("ghi789")
        pr = OpenPullRequest(
            pr_id=pr_id,
            head_sha=sha,
            title="Test",
            is_draft=False,
        )

        with pytest.raises(AttributeError):
            pr.is_draft = True
