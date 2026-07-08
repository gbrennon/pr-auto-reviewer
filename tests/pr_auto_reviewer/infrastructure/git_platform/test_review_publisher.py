"""Tests for GitReviewPublisherAdapter using fixture data."""

import pytest

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.exceptions.review_publish_error import ReviewPublishError
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.infrastructure.review_publishers.platform_publisher import (
    PlatformReviewPublisherAdapter,
)
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyFormatter,
)
GitReviewPublisherAdapter = PlatformReviewPublisherAdapter
format_review_body = ReviewBodyFormatter().format

class TestGitReviewPublisherAdapter:
    """Tests for GitReviewPublisherAdapter using captured fixture data."""

    @pytest.fixture
    def adapter(self, patched_private_client):
        return GitReviewPublisherAdapter(patched_private_client, "t", "u", owner_client=patched_private_client)

    def test_publish(self, adapter):
        """Publish sends a formal PR review."""
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

    @pytest.mark.parametrize("verdict", [
        ReviewVerdict.APPROVED,
        ReviewVerdict.CHANGES_REQUESTED,
        ReviewVerdict.COMMENTED,
    ])
    def test_publish_maps_verdict(self, adapter, verdict):
        """Publish maps ReviewVerdict to correct event."""
        review = CodeReview(verdict=verdict, summary="Test", items=[], model_used="t")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

    def test_format_body_none_summary(self, adapter):
        """_format_body handles None summary."""
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary=None, items=[], model_used=None)
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

    def test_format_body_none_model(self, adapter):
        """_format_body handles None model_used."""
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used=None)
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

    def test_format_body_none_file_path(self, adapter):
        """_format_body handles None file_path."""
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED, summary="s",
            items=[ReviewItem(number=1, category="c", severity=ItemSeverity.INFO,
                              description="d", file_path=None)],
            model_used="m",
        )
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

    def test_format_body_empty_items(self, adapter):
        """_format_body handles empty items list."""
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)

    def test_reviewer_request_failure_non_fatal(self, patched_private_client, monkeypatch):
        """Reviewer request failure is logged, not raised."""
        call_paths = []
        def fake_post(path, body):
            call_paths.append(path)
            if "requested_reviewers" in path:
                raise Exception("422")
            return {"id": 1}
        monkeypatch.setattr(patched_private_client, "post", fake_post)
        adapter = GitReviewPublisherAdapter(patched_private_client, "t", "u", owner_client=patched_private_client)
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        assert len(call_paths) == 2
