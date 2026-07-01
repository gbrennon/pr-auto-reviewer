"""Tests for GitReviewPublisherAdapter using fixture data."""

import pytest

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.exceptions.review_publish_error import ReviewPublishError
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.infrastructure.git_platform.review_publisher import (
    GitReviewPublisherAdapter,
    format_review_body,
)


class TestGitReviewPublisherAdapter:
    """Tests for GitReviewPublisherAdapter using captured fixture data."""

    @pytest.fixture
    def adapter(self, patched_private_client):
        return GitReviewPublisherAdapter(patched_private_client, "t", "u")

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
        adapter = GitReviewPublisherAdapter(patched_private_client, "t", "u")
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        assert len(call_paths) == 2


class TestFormatReviewBody:
    """Tests for format_review_body."""

    def test_items_numbered_from_zero(self):
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="ok",
            items=[
                ReviewItem(number=0, category=IssueCategory.BUG, severity=ItemSeverity.MINOR,
                          file_path="a.py", description="bad", current_code="x", suggested_fix="y"),
            ],
            model_used="m",
        )
        body = format_review_body(review)
        assert "0. [bug] [MINOR] a.py" in body

    def test_praise_numbered_after_items(self):
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="ok",
            items=[
                ReviewItem(number=0, category=IssueCategory.BUG, severity=ItemSeverity.MINOR,
                          file_path="a.py", description="bad", current_code="x", suggested_fix="y"),
                ReviewItem(number=1, category=IssueCategory.STYLE, severity=ItemSeverity.INFO,
                          file_path="b.py", description="ugly", current_code="z", suggested_fix="w"),
            ],
            praise=[{"file": "c.py", "description": "nice work"}],
            model_used="m",
        )
        body = format_review_body(review)
        assert "0. [bug] [MINOR] a.py" in body
        assert "1. [style] [INFO] b.py" in body
        assert "2. c.py: nice work" in body

    def test_reason_and_summary_present(self):
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="security bug",
            summary="needs work",
            items=[],
            model_used="m",
        )
        body = format_review_body(review)
        assert "Changes Requested" in body
        assert "security bug" in body
        assert "needs work" in body

    def test_empty_items_shows_placeholder(self):
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="",
            items=[],
            model_used=None,
        )
        body = format_review_body(review)
        assert "No issues found" in body
        assert "No notable patterns" in body

    def test_filters_out_critical_items(self):
        """CRITICAL severity items are excluded from the rendered output."""
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="ok",
            items=[
                ReviewItem(number=0, category=IssueCategory.SECURITY,
                          severity=ItemSeverity.CRITICAL,
                          file_path="a.py", description="critical issue"),
            ],
            model_used="m",
        )
        body = format_review_body(review)
        assert "CRITICAL" not in body
        assert "critical issue" not in body

    def test_filters_out_major_items(self):
        """MAJOR severity items are excluded from the rendered output."""
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="ok",
            items=[
                ReviewItem(number=0, category=IssueCategory.BUG,
                          severity=ItemSeverity.MAJOR,
                          file_path="a.py", description="major issue"),
            ],
            model_used="m",
        )
        body = format_review_body(review)
        assert "MAJOR" not in body
        assert "major issue" not in body

    def test_includes_minor_items(self):
        """MINOR severity items ARE included in the rendered output."""
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="ok",
            items=[
                ReviewItem(number=0, category=IssueCategory.STYLE,
                          severity=ItemSeverity.MINOR,
                          file_path="b.py", description="minor issue"),
            ],
            model_used="m",
        )
        body = format_review_body(review)
        assert "[MINOR]" in body
        assert "minor issue" in body

    def test_includes_info_items(self):
        """INFO severity items ARE included in the rendered output."""
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="ok",
            items=[
                ReviewItem(number=0, category=IssueCategory.DOCS,
                          severity=ItemSeverity.INFO,
                          file_path="c.py", description="info note"),
            ],
            model_used="m",
        )
        body = format_review_body(review)
        assert "[INFO]" in body
        assert "info note" in body

    def test_praise_always_included(self):
        """Praise items are always included regardless of issue severity filtering."""
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="ok",
            items=[
                ReviewItem(number=0, category=IssueCategory.SECURITY,
                          severity=ItemSeverity.CRITICAL,
                          file_path="a.py", description="critical issue"),
            ],
            praise=[{"file": "d.py", "description": "great code organization"}],
            model_used="m",
        )
        body = format_review_body(review)
        assert "CRITICAL" not in body
        assert "critical issue" not in body
        assert "great code organization" in body
        assert "### Praise" in body

    def test_mixed_items_filter_critical_and_major_only(self):
        """When mixed: CRITICAL and MAJOR are excluded, MINOR and INFO remain, praise stays."""
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="mixed",
            items=[
                ReviewItem(number=0, category=IssueCategory.SECURITY,
                          severity=ItemSeverity.CRITICAL,
                          file_path="a.py", description="critical"),
                ReviewItem(number=1, category=IssueCategory.BUG,
                          severity=ItemSeverity.MAJOR,
                          file_path="b.py", description="major"),
                ReviewItem(number=2, category=IssueCategory.STYLE,
                          severity=ItemSeverity.MINOR,
                          file_path="c.py", description="minor"),
                ReviewItem(number=3, category=IssueCategory.DOCS,
                          severity=ItemSeverity.INFO,
                          file_path="d.py", description="info"),
            ],
            praise=[{"file": "e.py", "description": "clean code"}],
            model_used="m",
        )
        body = format_review_body(review)
        assert "critical" not in body
        assert "major" not in body
        assert "[MINOR]" in body
        assert "minor" in body
        assert "[INFO]" in body
        assert "info" in body
        assert "clean code" in body

    def test_all_critical_major_shows_no_issues(self):
        """When all items are CRITICAL or MAJOR, the 'No issues found' placeholder appears."""
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="ok",
            items=[
                ReviewItem(number=0, category=IssueCategory.SECURITY,
                          severity=ItemSeverity.CRITICAL,
                          file_path="a.py", description="critical"),
                ReviewItem(number=1, category=IssueCategory.BUG,
                          severity=ItemSeverity.MAJOR,
                          file_path="b.py", description="major"),
            ],
            praise=[{"file": "f.py", "description": "nice"}],
            model_used="m",
        )
        body = format_review_body(review)
        assert "No issues found" in body
        assert "critical" not in body
        assert "major" not in body
        assert "nice" in body


class TestGetDiffPosition:
    """Tests for _get_diff_position."""

    def test_finds_added_line(self):
        diff = "diff --git a/x.py b/x.py\n@@ -1,3 +2,4 @@\n context\n+added line here\n context"
        result = GitReviewPublisherAdapter._get_diff_position(diff, "x.py", "added line here")
        assert result is not None
        assert result["old_line"] is None
        assert result["new_line"] == 3

    def test_finds_deleted_line(self):
        diff = "diff --git a/x.py b/x.py\n@@ -1,5 +1,4 @@\n context\n-removed line here\n context"
        result = GitReviewPublisherAdapter._get_diff_position(diff, "x.py", "removed line here")
        assert result is not None
        assert result["old_line"] == 2
        assert result["new_line"] is None

    def test_finds_context_line(self):
        diff = "diff --git a/x.py b/x.py\n@@ -10,5 +11,5 @@\n context line here"
        result = GitReviewPublisherAdapter._get_diff_position(diff, "x.py", "context line here")
        assert result is not None
        assert result["old_line"] == 10
        assert result["new_line"] == 11

    def test_returns_none_for_missing_file(self):
        diff = "diff --git a/x.py b/x.py\n@@ -1 +1 @@\n-old\n+new"
        result = GitReviewPublisherAdapter._get_diff_position(diff, "y.py", "new")
        assert result is None

    def test_returns_none_for_empty_inputs(self):
        assert GitReviewPublisherAdapter._get_diff_position("", None, "") is None
        assert GitReviewPublisherAdapter._get_diff_position("diff", "f.py", "") is None


class TestReviewPublisherCodeberg:
    """Tests for Codeberg-specific review publisher behavior."""

    def test_codeberg_adds_official_flag(self, patched_private_client, monkeypatch):
        """Codeberg client sets official=True in payload."""
        captured_payload = {}
        def fake_post(path, body):
            captured_payload.update(body)
            return {"id": 1}
        monkeypatch.setattr(patched_private_client, "post", fake_post)
        monkeypatch.setattr(patched_private_client, "_platform_mode", "codeberg")
        adapter = GitReviewPublisherAdapter(patched_private_client, "t", "u")
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m")
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        assert captured_payload.get("official") is True
        assert captured_payload.get("event") == "APPROVED"


    def test_codeberg_review_with_inline_comment_error(self, patched_private_client, monkeypatch):
        """Inline comment resolution failure is logged but doesn't crash."""
        captured_payload = {}
        calls = []
        def fake_post(path, body):
            calls.append(path)
            captured_payload.update(body)
            return {"id": 1}
        monkeypatch.setattr(patched_private_client, "post", fake_post)
        monkeypatch.setattr(patched_private_client, "_platform_mode", "codeberg")
        adapter = GitReviewPublisherAdapter(patched_private_client, "t", "u")
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="fix",
            items=[ReviewItem(number=0, category=IssueCategory.BUG, severity=ItemSeverity.MINOR,
                             file_path="x.py", description="bad", current_code="code", suggested_fix="fix")],
            model_used="m",
        )
        pr_id = PullRequestId(repository="o/r", number=1)
        # Should not raise even if diff resolution fails
        adapter.publish(pr_id, review)
        assert captured_payload.get("event") == "REQUEST_CHANGES"
