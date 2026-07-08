"""Tests for TerminalReviewPublisherAdapter."""

import pytest

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.infrastructure.review_publishers.terminal_publisher import (
    TerminalReviewPublisherAdapter,
)

_review_to_json = TerminalReviewPublisherAdapter._review_to_json

class TestReviewToJson:
    def test_serializes_full_review(self):
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="lgtm",
            summary="all good",
            items=[
                ReviewItem(number=0, category=IssueCategory.BUG, severity=ItemSeverity.MAJOR,
                          file_path="a.py", description="bad", current_code="x", suggested_fix="y"),
            ],
            praise=[{"file": "a.py", "description": "nice"}],
            model_used="test-model",
        )
        json_text = _review_to_json(review)
        assert '"verdict"' in json_text
        assert '"approved"' in json_text
        assert '"a.py"' in json_text
        assert '"test-model"' in json_text

class TestTerminalReviewPublisherAdapter:
    def test_writes_to_file(self, tmp_path, monkeypatch):
        out_file = tmp_path / "subdir" / "review.txt"
        adapter = TerminalReviewPublisherAdapter(output_path=str(out_file))
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED, summary="ok", items=[], model_used="m",
        )
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        assert out_file.exists()
        content = out_file.read_text()
        assert "Review for o/r#1" in content
        assert "--- HUMAN-READABLE ---" in content
        assert "--- JSON ---" in content

    def test_writes_to_stdout(self, capsys):
        adapter = TerminalReviewPublisherAdapter(output_path=None)
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED, summary="ok", items=[], model_used="m",
        )
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        captured = capsys.readouterr()
        assert "Review for o/r#1" in captured.out
        assert "--- JSON ---" in captured.out
