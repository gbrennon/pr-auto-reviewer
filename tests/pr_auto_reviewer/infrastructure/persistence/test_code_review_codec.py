from __future__ import annotations

import pytest

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions import RepositoryCorruptedError
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.persistence.code_review_codec import (
    CodeReviewCodec,
)
from pr_auto_reviewer.infrastructure.persistence.review_item_codec import (
    ReviewItemCodec,
)


def _review_payload() -> dict[str, object]:
    return {
        "verdict": "approved",
        "reason": "No blocking issues",
        "summary": "The change is ready.",
        "model_used": "test-model",
        "items": [],
        "suggestions": [],
        "praise": [],
    }


def _item_payload() -> dict[str, object]:
    return {
        "id": "item-1",
        "severity": "major",
        "category": "bug",
        "file_path": "src/app.py",
        "description": "item",
    }


class TestCodeReviewCodec:
    def test_serialize_review_with_items(self) -> None:
        item = ReviewItem(
            severity="major",
            category="correctness",
            file_path="src/app.py",
            description="item",
        )
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="reviewed",
            summary="No blocking issues",
            model_used="test-model",
            items=[item],
        )

        payload = CodeReviewCodec.serialize(review)

        assert payload["items"][0]["description"] == "item"

    def test_deserialize_accepts_explicit_clean_review(self) -> None:
        review = CodeReviewCodec.deserialize(_review_payload())

        assert review.verdict is ReviewVerdict.APPROVED
        assert review.reason == "No blocking issues"
        assert review.summary == "The change is ready."
        assert review.model_used == "test-model"
        assert review.items == []
        assert review.suggestions == []
        assert review.praise == []

    @pytest.mark.parametrize(
        "field",
        (
            "verdict",
            "reason",
            "summary",
            "model_used",
            "items",
            "suggestions",
            "praise",
        ),
    )
    def test_deserialize_rejects_missing_required_review_field(
        self, field: str
    ) -> None:
        payload = _review_payload()
        del payload[field]

        with pytest.raises(RepositoryCorruptedError):
            CodeReviewCodec.deserialize(payload)

    @pytest.mark.parametrize(
        ("field", "value"),
        (
            ("verdict", "commented"),
            ("verdict", "unknown"),
            ("reason", " "),
            ("summary", ""),
            ("model_used", "\t"),
        ),
    )
    def test_deserialize_rejects_blank_or_unknown_review_field(
        self, field: str, value: str
    ) -> None:
        payload = _review_payload()
        payload[field] = value

        with pytest.raises(RepositoryCorruptedError):
            CodeReviewCodec.deserialize(payload)

    @pytest.mark.parametrize("field", ("items", "suggestions", "praise"))
    def test_deserialize_rejects_non_list_collection(self, field: str) -> None:
        payload = _review_payload()
        payload[field] = {}

        with pytest.raises(RepositoryCorruptedError):
            CodeReviewCodec.deserialize(payload)

    @pytest.mark.parametrize("field", ("id", "severity", "category", "description"))
    def test_item_deserialize_rejects_missing_required_field(self, field: str) -> None:
        payload = _item_payload()
        del payload[field]

        with pytest.raises(RepositoryCorruptedError):
            ReviewItemCodec.deserialize(payload)

    @pytest.mark.parametrize(
        ("field", "value"),
        (
            ("id", " "),
            ("severity", "unknown"),
            ("category", "unknown"),
            ("description", ""),
        ),
    )
    def test_item_deserialize_rejects_invalid_required_field(
        self, field: str, value: str
    ) -> None:
        payload = _item_payload()
        payload[field] = value

        with pytest.raises(RepositoryCorruptedError):
            ReviewItemCodec.deserialize(payload)

    def test_item_deserialize_accepts_supplied_aliases(self) -> None:
        payload = _item_payload()
        payload["severity"] = "high"
        payload["category"] = "correctness"

        item = ReviewItemCodec.deserialize(payload)

        assert item.severity.value == "major"
        assert item.category.value == "bug"
