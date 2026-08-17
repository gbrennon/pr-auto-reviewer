"""Tests for IssueBodyBuilder domain service."""

from pr_auto_reviewer.application.serializers import IssueBodyBuilder
from pr_auto_reviewer.domain import (
    ItemSeverity,
    PullRequestId,
    ReviewItem,
)


class TestIssueBodyBuilder:
    """Tests for IssueBodyBuilder.build(pr_id, item) -> tuple[str, str]."""

    def test_basic_build_title_contains_severity_and_category(self) -> None:
        builder = IssueBodyBuilder()
        pr_id = PullRequestId(repository="owner/repo", number=42)
        item = ReviewItem(id="id-1",
            severity=ItemSeverity.CRITICAL,
            category="security",
            file_path="src/main.py",
            description="SQL injection vulnerability in login handler",
        )
        title, _ = builder.build(pr_id, item)
        assert "CRITICAL" in title
        assert "security" in title

    def test_basic_build_body_contains_all_fields(self) -> None:
        builder = IssueBodyBuilder()
        pr_id = PullRequestId(repository="owner/repo", number=42)
        item = ReviewItem(id="id-3",
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="src/utils.py",
            description="Off-by-one error in loop boundary",
        )
        _, body = builder.build(pr_id, item)
        assert "owner/repo#42" in body
        assert "Review Item id-3" in body
        assert "MAJOR" in body
        assert "bug" in body
        assert "`src/utils.py`" in body
        assert "Off-by-one error in loop boundary" in body

    def test_file_path_none_shows_no_specific_file(self) -> None:
        builder = IssueBodyBuilder()
        pr_id = PullRequestId(repository="owner/repo", number=1)
        item = ReviewItem(id="id-2",
            severity=ItemSeverity.INFO,
            category="style",
            file_path=None,
            description="Consider using f-strings",
        )
        _, body = builder.build(pr_id, item)
        assert "_(no specific file)_" in body
        assert "`" not in body.split("**File:**")[1].split("\n")[0]

    def test_severity_is_uppercase_in_output(self) -> None:
        builder = IssueBodyBuilder()
        pr_id = PullRequestId(repository="owner/repo", number=1)
        item = ReviewItem(id="id-1",
            severity=ItemSeverity.MINOR,
            category="docs",
            file_path="README.md",
            description="Fix typo",
        )
        title, body = builder.build(pr_id, item)
        assert "[MINOR]" in title
        assert "MINOR" in body
        assert "minor" not in title

    def test_title_truncates_description_at_80_chars(self) -> None:
        builder = IssueBodyBuilder()
        pr_id = PullRequestId(repository="owner/repo", number=1)
        long_desc = "A" * 200
        item = ReviewItem(id="id-1",
            severity=ItemSeverity.INFO,
            category="general",
            file_path=None,
            description=long_desc,
        )
        title, body = builder.build(pr_id, item)
        prefix = "[INFO] general: "
        assert title.startswith(prefix)
        desc_part = title[len(prefix):]
        assert len(desc_part) == 80
        assert desc_part == long_desc[:80]
        assert long_desc in body

    def test_title_uses_full_description_when_short(self) -> None:
        builder = IssueBodyBuilder()
        pr_id = PullRequestId(repository="owner/repo", number=1)
        short_desc = "Fix typo"
        item = ReviewItem(id="id-1",
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description=short_desc,
        )
        title, _ = builder.build(pr_id, item)
        assert title.endswith(short_desc)

    def test_body_contains_formatted_location_with_file_path(self) -> None:
        builder = IssueBodyBuilder()
        pr_id = PullRequestId(repository="owner/repo", number=1)
        item = ReviewItem(id="id-1",
            severity=ItemSeverity.CRITICAL,
            category="security",
            file_path="src/auth/login.py",
            description="Hardcoded secret",
        )
        _, body = builder.build(pr_id, item)
        assert "- **File:** `src/auth/login.py`" in body

    def test_body_includes_current_code_and_suggested_fix(self) -> None:
        builder = IssueBodyBuilder()
        pr_id = PullRequestId(repository="owner/repo", number=1)
        item = ReviewItem(id="id-1",
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="src/main.py",
            description="Off-by-one error",
            current_code="for i in range(len(items)):",
            suggested_fix="for item in items:",
        )
        _, body = builder.build(pr_id, item)
        assert "### Current Code" in body
        assert "for i in range(len(items)):" in body
        assert "### Suggested Fix" in body
        assert "for item in items:" in body
