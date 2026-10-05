from ._helpers import *


class TestIssuesCreatedMessage:
    """Tests for issues_created_message(issues, review_items) -> str."""

    def test_formats_single_issue(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        issue = Issue(
            id=101,
            repository="owner/repo",
            title="[CRITICAL] security: SQL injection risk",
            body="Full body",
            source_pr_id=pr_id,
            source_item_id="id-1",
        )
        item = ReviewItem(
            id="id-1",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="x.py",
            description="broken",
            status=ReviewItemStatus.OPEN,
        )

        result = issues_created_message([issue], [item])

        assert "Created 1 issue(s):" in result
        assert "- #101: [CRITICAL] security: SQL injection risk" in result
        assert (
            "  - review item `id-1` (major bug, blocking) — status: open (still relevant)"
            in result
        )

    def test_formats_multiple_issues(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        issue1 = Issue(
            id=101, repository="owner/repo",
            title="[CRITICAL] security: SQL injection",
            body="b1", source_pr_id=pr_id, source_item_id="id-1",
        )
        issue2 = Issue(
            id=102, repository="owner/repo",
            title="[MINOR] docs: Typo",
            body="b2", source_pr_id=pr_id, source_item_id="id-2",
        )
        item1 = ReviewItem(
            id="id-1", severity=ItemSeverity.CRITICAL,
            category=IssueCategory.SECURITY,
            file_path="a.py", description="SQL injection", status=ReviewItemStatus.OPEN,
        )
        item2 = ReviewItem(
            id="id-2", severity=ItemSeverity.MINOR,
            category=IssueCategory.DOCS,
            file_path="b.py", description="Typo", status=ReviewItemStatus.OPEN,
        )

        result = issues_created_message([issue1, issue2], [item1, item2])

        assert "Created 2 issue(s):" in result
        assert "- #101: [CRITICAL] security: SQL injection" in result
        assert (
            "  - review item `id-1` (critical security, blocking) — status: open (still relevant)"
            in result
        )
        assert "- #102: [MINOR] docs: Typo" in result
        assert (
            "  - review item `id-2` (minor docs, non-blocking) — status: open (still relevant)"
            in result
        )

    def test_empty_issues_list(self) -> None:
        issues: list[Issue] = []
        review_items: list[ReviewItem] = []

        result = issues_created_message(issues, review_items)

        assert "Created 0 issue(s):" in result

    def test_marks_resolved_item_no_longer_relevant(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        issue = Issue(
            id=101,
            repository="owner/repo",
            title="[MINOR] style: Rename variable",
            body="body",
            source_pr_id=pr_id,
            source_item_id="id-1",
        )
        item = ReviewItem(
            id="id-1",
            severity=ItemSeverity.MINOR,
            category=IssueCategory.STYLE,
            file_path="src/main.py",
            description="Rename variable",
            status=ReviewItemStatus.RESOLVED,
        )

        result = issues_created_message([issue], [item])

        assert "status: resolved (no longer relevant)" in result

    def test_missing_review_item_renders_unknown_status(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        issue = Issue(
            id=101,
            repository="owner/repo",
            title="[MINOR] style: Missing item",
            body="body",
            source_pr_id=pr_id,
            source_item_id="missing-id",
        )
        items: list[ReviewItem] = []

        result = issues_created_message([issue], items)

        assert "status: unknown (no longer in the latest review)" in result
        assert "review item `missing-id`" in result
