import pytest
from pr_auto_reviewer.domain import (
    CodeReview,
    ReviewVerdict,
    ReviewItem,
    ItemSeverity,
)


class TestCodeReview:
    """Tests for CodeReview value object."""

    def test_creation_with_items(self) -> None:
        items = [
            ReviewItem(
                number=1,
                severity=ItemSeverity.CRITICAL,
                category="security",
                file_path="x.py",
                description="Fix SQL injection",
            ),
        ]
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="Security issue found",
            items=items,
            model_used="llama3",
        )
        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert review.summary == "Security issue found"
        assert len(review.items) == 1
        assert review.model_used == "llama3"

    def test_creation_minimal(self) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="LGTM",
        )
        assert review.items == []
        assert review.model_used == ""

    def test_equality_same(self) -> None:
        a = CodeReview(verdict=ReviewVerdict.APPROVED, summary="OK")
        b = CodeReview(verdict=ReviewVerdict.APPROVED, summary="OK")
        assert a == b

    def test_equality_different_verdict(self) -> None:
        a = CodeReview(verdict=ReviewVerdict.APPROVED, summary="OK")
        b = CodeReview(verdict=ReviewVerdict.CHANGES_REQUESTED, summary="OK")
        assert a != b

    def test_equality_different_items(self) -> None:
        item = ReviewItem(
            number=1,
            severity=ItemSeverity.MINOR,
            category="style",
            file_path="x.py",
            description="desc",
        )
        a = CodeReview(verdict=ReviewVerdict.APPROVED, summary="OK", items=[item])
        b = CodeReview(verdict=ReviewVerdict.APPROVED, summary="OK", items=[])
        assert a != b

    def test_immutability(self) -> None:
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="OK")
        with pytest.raises(Exception):
            review.summary = "changed"  # type: ignore[misc]

    def test_hash_consistency(self) -> None:
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="OK")
        # Frozen dataclass would auto-generate __hash__, but list[ReviewItem]
        # makes it unhashable. This is expected for VOs with collection fields.
        # Two identical CodeReviews are still equal via __eq__.
        with pytest.raises(TypeError, match="unhashable"):
            hash(review)
