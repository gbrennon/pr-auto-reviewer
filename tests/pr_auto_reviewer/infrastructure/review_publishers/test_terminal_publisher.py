"""Tests for TerminalReviewPublisherAdapter — final JSON output hygiene."""

import json
from pathlib import Path

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.review_publishers.terminal_publisher import (
    TerminalReviewPublisherAdapter,
)
from tests.fakes.fake_review_body_renderer_factory import FakeReviewBodyRendererFactory

_BODY = FakeReviewBodyRendererFactory.make()


class TestTerminalPublisher:
    """Final JSON output must never contain empty nested fields."""

    def _publish_json(self, tmp_path: Path, review: CodeReview) -> dict:
        out_file = tmp_path / "review.txt"
        adapter = TerminalReviewPublisherAdapter(
            body_renderer=_BODY,
            output_path=str(out_file),
        )
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.publish(pr_id, review)
        mark = "--- JSON ---\n"
        content = out_file.read_text()
        payload = content.split(mark, 1)[1].split("\n===", 1)[0]
        return json.loads(payload)

    def test_full_review_has_no_empty_values(self, tmp_path: Path) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="lacks error handling",
            summary="lacks error handling",
            items=[
                ReviewItem(
                    severity=ItemSeverity.MAJOR,
                    category=IssueCategory.MAINTAINABILITY,
                    file_path="src/a.py",
                    description="Missing validation.",
                    line="10-14",
                    id="ab12",
                    current_code="def f():",
                    suggested_fix="Add validation.",
                ),
            ],
            suggestions=[ReviewItem(
                    severity="info",
                    category="general",
                    file_path="src/a.py",
                    line="10-14",
                    description="Add validation.",
                    current_code="def f():",
                    suggested_fix="Add validation.",
                )],
            praise=[ReviewItem(
                    severity="info",
                    category="general",
                    file_path="",
                    description="Good structure.",
                    line="",
                    id="",
                    current_code="",
                    suggested_fix="Good structure.",
                )],
            model_used="code-review:latest",
        )
        payload = self._publish_json(tmp_path, review)
        assert payload["verdict"] == "changes_requested"
        assert payload["reason"] != ""
        assert payload["summary"] != ""
        assert payload["items"] != []
        assert payload["suggestions"] != []
        assert payload["praise"] != []
        assert payload["model_used"] != ""

        def _assert_no_empty(value):
            if isinstance(value, dict):
                for key, val in value.items():
                    assert val not in ("", None), f"empty {key}={val!r}"
                    _assert_no_empty(val)
            elif isinstance(value, list):
                for val in value:
                    _assert_no_empty(val)

        _assert_no_empty(payload)

    def test_string_suggestion_omits_empty_code_fields(self, tmp_path: Path) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="ok",
            summary="ok",
            suggestions=[ReviewItem(
                    severity="info",
                    category="general",
                    file_path="",
                    description="Implement rate limiting for LLM calls",
                    line="",
                    id="",
                    current_code="",
                    suggested_fix="Implement rate limiting for LLM calls",
                )],
            model_used="m",
        )
        payload = self._publish_json(tmp_path, review)
        suggestion = payload["suggestions"][0]
        assert suggestion["description"]
        assert "current_code" not in suggestion
        assert "suggested_code" not in suggestion
        assert "file" not in suggestion
        assert "line" not in suggestion

    def test_praise_omits_empty_file(self, tmp_path: Path) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="ok",
            summary="ok",
            praise=[ReviewItem(
                    severity="info",
                    category="general",
                    file_path="",
                    description="Good structure.",
                    line="",
                    id="",
                    current_code="",
                    suggested_fix="Good structure.",
                )],
            model_used="m",
        )
        payload = self._publish_json(tmp_path, review)
        praise = payload["praise"][0]
        assert praise["description"]
        assert "file" not in praise