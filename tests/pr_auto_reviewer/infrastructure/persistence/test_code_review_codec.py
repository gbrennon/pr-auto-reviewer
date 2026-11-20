from __future__ import annotations

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.persistence.code_review_codec import (
    CodeReviewCodec,
)


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
