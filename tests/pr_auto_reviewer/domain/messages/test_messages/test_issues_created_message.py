from ._helpers import *


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
            source_item_id="id-1",
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
                source_item_id="id-1",
            ),
            Issue(
                id=102,
                repository="owner/repo",
                title="[MAJOR] bug: Off-by-one",
                body="body 2",
                source_pr_id=pr_id,
                source_item_id="id-2",
            ),
            Issue(
                id=103,
                repository="owner/repo",
                title="[MINOR] docs: Typo",
                body="body 3",
                source_pr_id=pr_id,
                source_item_id="id-3",
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

