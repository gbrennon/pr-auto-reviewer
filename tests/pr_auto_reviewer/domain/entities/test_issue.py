from dataclasses import FrozenInstanceError

import pytest

from pr_auto_reviewer.domain import (
    InvalidIssueBodyError,
    Issue,
    PullRequestId,
)


class TestIssue:
    """Tests for Issue entity (immutable)."""

    def test_creation(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        issue = Issue(
            id=100,
            repository="owner/repo",
            title="Fix SQL injection in main.py",
            body="## Review Item 1\n\nFound a security issue...",
            source_pr_id=pr_id,
            source_item_number=3,
        )
        assert issue.id == 100
        assert issue.repository == "owner/repo"
        assert issue.title == "Fix SQL injection in main.py"
        assert "security" in issue.body
        assert issue.source_pr_id == pr_id
        assert issue.source_item_number == 3

    def test_identity_by_id(self) -> None:
        pr_id = PullRequestId(repository="r", number=1)
        a = Issue(
            id=100, repository="r", title="Issue A", body="body A",
            source_pr_id=pr_id, source_item_number=1,
        )
        b = Issue(
            id=200, repository="r", title="Issue A", body="body A",
            source_pr_id=pr_id, source_item_number=1,
        )
        assert a.id != b.id

    def test_different_source_pr(self) -> None:
        pr_a = PullRequestId(repository="owner/repo", number=42)
        pr_b = PullRequestId(repository="other/repo", number=99)

        issue_a = Issue(
            id=1, repository="r", title="t", body="b",
            source_pr_id=pr_a, source_item_number=1,
        )
        issue_b = Issue(
            id=2, repository="r", title="t", body="b",
            source_pr_id=pr_b, source_item_number=1,
        )
        assert issue_a.source_pr_id == pr_a
        assert issue_b.source_pr_id == pr_b
        assert issue_a.source_pr_id != issue_b.source_pr_id

    def test_close_and_is_closed(self) -> None:
        pr_id = PullRequestId(repository="r", number=1)
        original = Issue(
            id=100, repository="r", title="t", body="b",
            source_pr_id=pr_id, source_item_number=1,
        )
        assert original.is_closed() is False
        closed = original.close()
        assert original.is_closed() is False
        assert closed.is_closed() is True

    def test_update_body(self) -> None:
        pr_id = PullRequestId(repository="r", number=1)
        original = Issue(
            id=100, repository="r", title="t", body="original body",
            source_pr_id=pr_id, source_item_number=1,
        )
        updated = original.update_body("updated body")
        assert original.body == "original body"
        assert updated.body == "updated body"

    def test_update_body_rejects_empty(self) -> None:
        pr_id = PullRequestId(repository="r", number=1)
        issue = Issue(
            id=100, repository="r", title="t", body="b",
            source_pr_id=pr_id, source_item_number=1,
        )
        with pytest.raises(InvalidIssueBodyError, match="non-empty"):
            issue.update_body("")

    def test_close_idempotent(self) -> None:
        pr_id = PullRequestId(repository="r", number=1)
        issue = Issue(
            id=100, repository="r", title="t", body="b",
            source_pr_id=pr_id, source_item_number=1,
        )
        issue = issue.close()
        issue = issue.close()
        assert issue.is_closed() is True

    def test_immutable_id(self) -> None:
        pr_id = PullRequestId(repository="r", number=1)
        issue = Issue(
            id=100, repository="r", title="t", body="b",
            source_pr_id=pr_id, source_item_number=1,
        )
        with pytest.raises(FrozenInstanceError):
            issue.id = 200

    def test_immutable_source_pr_id(self) -> None:
        pr_id = PullRequestId(repository="r", number=1)
        issue = Issue(
            id=100, repository="r", title="t", body="b",
            source_pr_id=pr_id, source_item_number=1,
        )
        with pytest.raises(FrozenInstanceError):
            issue.source_pr_id = PullRequestId(repository="x", number=99)
