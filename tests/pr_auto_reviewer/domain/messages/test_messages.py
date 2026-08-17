"""Tests for message-building domain functions."""

from pr_auto_reviewer.domain import (
    Issue,
    ItemSeverity,
    PullRequestId,
    ReviewItem,
)
from pr_auto_reviewer.domain.messages import (
    invalid_items_message,
    issues_created_message,
)


class TestInvalidItemsMessage:
    """Tests for invalid_items_message(invalid, available) -> str."""

    def test_formats_invalid_numbers(self) -> None:
        invalid = [1, 3, 5]
        available: list[ReviewItem] = []
        result = invalid_items_message(invalid, available)
        assert "#1, #3, #5" in result

    def test_formats_available_items(self) -> None:
        invalid: list[int] = []
        available = [
            ReviewItem(
                number=1,
                severity=ItemSeverity.CRITICAL,
                category="security",
                file_path="src/main.py",
                description="SQL injection risk",
            ),
            ReviewItem(
                number=2,
                severity=ItemSeverity.MAJOR,
                category="bug",
                file_path=None,
                description="Off-by-one error",
            ),
        ]
        result = invalid_items_message(invalid, available)
        assert "Available items:" in result
        assert "- #1: SQL injection risk..." in result
        assert "- #2: Off-by-one error..." in result

    def test_full_message_with_both_invalid_and_available(self) -> None:
        invalid = [4, 5]
        available = [
            ReviewItem(
                number=1,
                severity=ItemSeverity.INFO,
                category="style",
                file_path=None,
                description="Use type hints throughout the module",
            ),
        ]
        result = invalid_items_message(invalid, available)
        assert "Could not find review items: #4, #5." in result
        assert "Available items:" in result
        assert "- #1: Use type hints throughout the module..." in result

    def test_description_truncated_at_60_chars(self) -> None:
        invalid: list[int] = []
        long_desc = "X" * 100
        available = [
            ReviewItem(
                number=1,
                severity=ItemSeverity.INFO,
                category="general",
                file_path=None,
                description=long_desc,
            ),
        ]
        result = invalid_items_message(invalid, available)
        expected_desc = long_desc[:60] + "..."
        assert f"- #1: {expected_desc}" in result

    def test_single_invalid_item(self) -> None:
        result = invalid_items_message([7], [])
        assert "#7." in result
        assert "#7," not in result

class TestIssuesCreatedMessage:
    """Tests for issues_created_message(issues) -> str."""

    def test_formats_single_issue(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        issue = Issue(
            id=101,
            repository="owner/repo",
            title="[CRITICAL] security: SQL injection risk",
            body="Full body",
            source_pr_id=pr_id,
            source_item_number=1,
        )
        result = issues_created_message([issue])
        assert "Created 1 issue(s):" in result
        assert "- #101: [CRITICAL] security: SQL injection risk" in result

    def test_formats_multiple_issues(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        issues = [
            Issue(
                id=101,
                repository="owner/repo",
                title="[CRITICAL] security: SQL injection",
                body="body 1",
                source_pr_id=pr_id,
                source_item_number=1,
            ),
            Issue(
                id=102,
                repository="owner/repo",
                title="[MAJOR] bug: Off-by-one",
                body="body 2",
                source_pr_id=pr_id,
                source_item_number=2,
            ),
            Issue(
                id=103,
                repository="owner/repo",
                title="[MINOR] docs: Typo",
                body="body 3",
                source_pr_id=pr_id,
                source_item_number=3,
            ),
        ]
        result = issues_created_message(issues)
        assert "Created 3 issue(s):" in result
        assert "- #101: [CRITICAL] security: SQL injection" in result
        assert "- #102: [MAJOR] bug: Off-by-one" in result
        assert "- #103: [MINOR] docs: Typo" in result

    def test_empty_issues_list(self) -> None:
        result = issues_created_message([])
        assert "Created 0 issue(s):" in result
