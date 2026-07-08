from pr_auto_reviewer.domain import IssueCategory

class TestIssueCategory:
    """Tests for IssueCategory enum."""

    def test_members_exist(self) -> None:
        assert IssueCategory.BUG == "bug"
        assert IssueCategory.SECURITY == "security"
        assert IssueCategory.DESIGN == "design"
        assert IssueCategory.PERFORMANCE == "performance"
        assert IssueCategory.TESTABILITY == "testability"
        assert IssueCategory.QUALITY == "quality"
        assert IssueCategory.DOCUMENTATION == "documentation"
        assert IssueCategory.TEST == "test"
        assert IssueCategory.TYPO == "typo"
        assert IssueCategory.MAINTAINABILITY == "maintainability"
        assert IssueCategory.STYLE == "style"
        assert IssueCategory.DOCS == "docs"
        assert IssueCategory.NAMING == "naming"
        assert IssueCategory.GENERAL == "general"

    def test_from_value_accepts_canonical_values(self) -> None:
        assert IssueCategory.from_value("security") == IssueCategory.SECURITY
        assert IssueCategory.from_value("style") == IssueCategory.STYLE

    def test_from_value_accepts_legacy_aliases(self) -> None:
        assert IssueCategory.from_value("architecture") == IssueCategory.DESIGN
        assert IssueCategory.from_value("solid") == IssueCategory.DESIGN
        assert IssueCategory.from_value("doc") == IssueCategory.DOCS

    def test_unknown_value_defaults_to_general(self) -> None:
        assert IssueCategory.from_value("not-a-category") == IssueCategory.GENERAL
