"""Tests for TerminalReviewPublisherAdapter."""

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.entities.review_suggestion import ReviewSuggestion
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.review_publishers.terminal_publisher import (
    TerminalReviewPublisherAdapter,
)

adapter = TerminalReviewPublisherAdapter()

class TestReviewToJson:
    def test_serializes_full_review(self):
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="lgtm",
            summary="all good",
            items=[
                ReviewItem(id="t0", category=IssueCategory.BUG, severity=ItemSeverity.MAJOR,
                          file_path="a.py", description="bad", current_code="x", suggested_fix="y"),
            ],
            praise=[ReviewSuggestion(file="a.py", description="nice")],
            model_used="test-model",
        )
        json_text = adapter._review_to_json(review)
        assert '"verdict"' in json_text
        assert '"approved"' in json_text
        assert '"a.py"' in json_text
        assert '"test-model"' in json_text
