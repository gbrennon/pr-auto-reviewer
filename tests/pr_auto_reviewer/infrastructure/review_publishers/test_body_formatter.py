"""Tests for ReviewBodyRenderer using captured fixture data."""

from pathlib import Path

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.entities.review_praise import ReviewPraise
from pr_auto_reviewer.domain.entities.review_suggestion import ReviewSuggestion
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import ReviewBodyRenderer

from tests.fixtures.body_formatter_fixtures import BodyFormatterFixtures as F


class TestReviewBodyRenderer:
    def test_format_review_with_items(self):
        renderer = ReviewBodyRenderer(template_dir=Path("src/pr_auto_reviewer/infrastructure/templates"))
        review = F.review_with_items()
        result = renderer.render(review)
        assert "CHANGES_REQUESTED" in result or "Changes Requested" in result
        assert "Null pointer" in result
        assert "f-string" in result

    def test_format_empty_review(self):
        renderer = ReviewBodyRenderer(template_dir=Path("src/pr_auto_reviewer/infrastructure/templates"))
        review = F.review_empty()
        result = renderer.render(review)
        assert "APPROVED" in result or "Approved" in result