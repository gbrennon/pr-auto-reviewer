"""Fixtures for ReviewBodyFormatter — captured from real CodeReview objects."""

from __future__ import annotations

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.entities.review_suggestion import ReviewSuggestion
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


class BodyFormatterFixtures:
    """CodeReview objects captured from real review outputs."""

    @staticmethod
    def review_with_items() -> CodeReview:
        """A review with items, praise, and suggestions — typical real output."""
        return CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            model_used="code-review:latest",
            summary="Found several issues that need attention.",
            items=[
                ReviewItem(
                    number=0,
                    severity=ItemSeverity.MAJOR,
                    category=IssueCategory.BUG,
                    file_path="src/app.py",
                    line=42,
                    description="Null pointer dereference possible",
                    current_code="result = obj.method()",
                    suggested_fix="if obj is not None:\n    result = obj.method()",
                ),
                ReviewItem(
                    number=1,
                    severity=ItemSeverity.MINOR,
                    category=IssueCategory.STYLE,
                    file_path="src/utils.py",
                    line=15,
                    description="Use f-string instead of format()",
                    current_code='msg = "Hello {}".format(name)',
                    suggested_fix='msg = f"Hello {name}"',
                ),
            ],
            praise=[ReviewSuggestion(description="Clean separation of concerns")],
            suggestions=[ReviewSuggestion(description="Consider adding integration tests")],
        )

    @staticmethod
    def review_empty() -> CodeReview:
        """A review with no items, praise, or suggestions — approved PR."""
        return CodeReview(
            verdict=ReviewVerdict.APPROVED,
            model_used="code-review:latest",
            summary="Looks good!",
        )
