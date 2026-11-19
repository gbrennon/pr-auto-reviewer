"""Tests for persisted review collections."""

from pr_auto_reviewer.domain import CodeReview, ItemSeverity, ReviewItem, ReviewVerdict
from pr_auto_reviewer.infrastructure.persistence.code_review_codec import CodeReviewCodec


class TestCodeReviewCodec:
    """Verify every review item collection can be serialized and restored."""

    @staticmethod
    def _item(item_id: str) -> ReviewItem:
        return ReviewItem(
            id=item_id,
            severity=ItemSeverity.MINOR,
            category="bug",
            file_path="src/example.py",
            description=f"Description for {item_id}",
        )

    def test_serializes_and_deserializes_all_item_collections(self) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="No blocking issues",
            reason="The change is safe",
            model_used="test-model",
            items=[self._item("item")],
            suggestions=[self._item("suggestion")],
            praise=[self._item("praise")],
        )

        restored = CodeReviewCodec.deserialize(CodeReviewCodec.serialize(review))

        assert restored == review
