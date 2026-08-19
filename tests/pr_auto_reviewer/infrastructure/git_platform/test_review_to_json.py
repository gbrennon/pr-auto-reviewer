"""Tests for ReviewJsonSerializer full-field JSON serialization."""

import json

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.review_publishers.review_json_serializer import (
    ReviewJsonSerializer,
)


def _full_review() -> CodeReview:
    return CodeReview(
        verdict=ReviewVerdict.CHANGES_REQUESTED,
        reason="Found issues.",
        summary="Review summary",
        items=[
            ReviewItem(
                id="t0",
                category=IssueCategory.BUG,
                severity=ItemSeverity.MAJOR,
                file_path="a.py",
                description="bad logic",
                line="12",
                current_code="x = 1",
                suggested_fix="x = 2",
            ),
        ],
        suggestions=[
            ReviewItem(
                severity="info",
                category="general",
                file_path="b.py",
                description="rename variable",
                line="3",
                id="s0",
                current_code="tmp",
                suggested_fix="count",
            ),
        ],
        praise=[ReviewItem(
            severity="info",
            category="general",
            file_path="c.py",
            description="great design",
            line="",
            id="",
            current_code="",
            suggested_fix="great design",
        )],
        model_used="test-model",
    )


class TestReviewJsonSerializer:
    """Behaviour of ReviewJsonSerializer.serialize(review) -> str."""

    def test_serializes_all_top_level_fields(self) -> None:
        data = json.loads(ReviewJsonSerializer().serialize(_full_review()))
        assert data["verdict"] == "changes_requested"
        assert data["reason"] == "Found issues."
        assert data["summary"] == "Review summary"
        assert data["model_used"] == "test-model"
        assert data["items"] != []
        assert data["suggestions"] != []
        assert data["praise"] != []

    def test_serializes_nested_item_fields(self) -> None:
        data = json.loads(ReviewJsonSerializer().serialize(_full_review()))
        item = data["items"][0]
        assert item == {
            "severity": "major",
            "category": "bug",
            "file_path": "a.py",
            "description": "bad logic",
            "line": "12",
            "id": "t0",
            "current_code": "x = 1",
            "suggested_fix": "x = 2",
        }

    def test_serializes_nested_suggestion_fields(self) -> None:
        data = json.loads(ReviewJsonSerializer().serialize(_full_review()))
        suggestion = data["suggestions"][0]
        assert suggestion == {
            "severity": "info",
            "category": "general",
            "file_path": "b.py",
            "description": "rename variable",
            "line": "3",
            "id": "s0",
            "current_code": "tmp",
            "suggested_fix": "count",
        }

    def test_serializes_nested_praise_fields(self) -> None:
        data = json.loads(ReviewJsonSerializer().serialize(_full_review()))
        assert data["praise"] == [{"severity": "info", "category": "general", "file_path": "c.py", "description": "great design", "suggested_fix": "great design"}]

    def test_top_level_empty_fields_are_preserved_as_empty(self) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="",
            summary="",
            items=[],
            suggestions=[],
            praise=[],
            model_used="",
        )
        data = json.loads(ReviewJsonSerializer().serialize(review))
        assert data["reason"] == ""
        assert data["summary"] == ""
        assert data["model_used"] == ""
        assert data["items"] == []
        assert data["suggestions"] == []
        assert data["praise"] == []

    def test_serializes_item_without_optionals(self) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.COMMENTED,
            reason="comment only",
            summary="",
            items=[
                ReviewItem(
                    id="t1",
                    category=IssueCategory.GENERAL,
                    severity=ItemSeverity.INFO,
                    file_path=None,
                    description="nits",
                ),
            ],
            suggestions=[],
            praise=[],
            model_used="",
        )
        data = json.loads(ReviewJsonSerializer().serialize(review))
        item = data["items"][0]
        assert "file_path" not in item
        assert "line" not in item
        assert "current_code" not in item
        assert "suggested_fix" not in item
        assert item["description"] == "nits"

    def test_each_item_serialized_with_non_empty_id(self) -> None:
        data = json.loads(ReviewJsonSerializer().serialize(_full_review()))
        for item in data["items"]:
            assert item.get("id")

    def test_serializes_to_valid_json_document(self) -> None:
        payload = ReviewJsonSerializer().serialize(_full_review())
        assert json.loads(payload)