"""Tests for ReviewBodyFormatter using captured fixture data."""

from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyFormatter,
)
from tests.fixtures.body_formatter_fixtures import BodyFormatterFixtures as F


class TestReviewBodyFormatter:
    def test_format_review_with_items(self):
        formatter = ReviewBodyFormatter()
        review = F.review_with_items()
        result = formatter.format(review)
        assert "CHANGES_REQUESTED" in result or "Changes Requested" in result
        assert "Null pointer" in result
        assert "f-string" in result

    def test_format_empty_review(self):
        formatter = ReviewBodyFormatter()
        review = F.review_empty()
        result = formatter.format(review)
        assert "APPROVED" in result or "Approved" in result
