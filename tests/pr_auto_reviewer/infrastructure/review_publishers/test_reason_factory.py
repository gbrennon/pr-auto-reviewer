"""Tests for ReasonFactory.make(items) -> str."""

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.infrastructure.review_publishers.reason_factory import (
    ReasonFactory,
)


def _review_item(
    severity: ItemSeverity,
    category: IssueCategory,
) -> ReviewItem:
    return ReviewItem(
        severity=severity,
        category=category,
        file_path="x.py",
        description="A finding.",
    )


class TestReasonFactory:
    """Behaviour of ReasonFactory.make(items) -> str."""

    def test_make_empty_items_returns_no_issues_found(self) -> None:
        factory = ReasonFactory()
        assert factory.make([]) == "No issues found."

    def test_make_single_group_returns_singular_sentence(self) -> None:
        factory = ReasonFactory()
        items = [_review_item(ItemSeverity.MINOR, IssueCategory.BUG)]
        assert factory.make(items) == "Found 1 minor (1 bug)."

    def test_make_two_groups_joins_with_and(self) -> None:
        factory = ReasonFactory()
        items = [
            _review_item(ItemSeverity.MINOR, IssueCategory.BUG),
            _review_item(ItemSeverity.CRITICAL, IssueCategory.SECURITY),
        ]
        assert factory.make(items) == (
            "Found 1 critical (1 security) and 1 minor (1 bug)."
        )

    def test_make_three_groups_uses_oxford_style(self) -> None:
        factory = ReasonFactory()
        items = [
            _review_item(ItemSeverity.CRITICAL, IssueCategory.SECURITY),
            _review_item(ItemSeverity.MINOR, IssueCategory.BUG),
            _review_item(ItemSeverity.INFO, IssueCategory.GENERAL),
        ]
        assert factory.make(items) == (
            "Found 1 critical (1 security), 1 minor (1 bug), and 1 info (1 general)."
        )

    def test_make_counts_categories_alphabetically_within_severity(self) -> None:
        factory = ReasonFactory()
        items = [
            _review_item(ItemSeverity.MINOR, IssueCategory.STYLE),
            _review_item(ItemSeverity.MINOR, IssueCategory.BUG),
        ]
        assert factory.make(items) == "Found 2 minor (1 bug, 1 style)."

    def test_make_skips_empty_severity_groups(self) -> None:
        factory = ReasonFactory()
        items = [
            _review_item(ItemSeverity.MAJOR, IssueCategory.PERFORMANCE),
            _review_item(ItemSeverity.INFO, IssueCategory.DOCS),
        ]
        assert factory.make(items) == (
            "Found 1 major (1 performance) and 1 info (1 docs)."
        )
