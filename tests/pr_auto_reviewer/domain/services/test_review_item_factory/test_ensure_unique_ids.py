from ._helpers import *


class TestEnsureUniqueIds:
    """Tests for ReviewItemFactory.ensure_unique_ids."""

    def _item(self, id: str) -> ReviewItem:
        return ReviewItem(
            severity=ItemSeverity.INFO,
            category=IssueCategory.GENERAL,
            file_path=None,
            description="",
            id=id,
        )

    def test_duplicate_and_empty_ids_become_globally_unique(self) -> None:
        """Items, suggestions, and praise share one id space with no collisions."""
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            items=[self._item("a1"), self._item("a1"), self._item("")],
            suggestions=[self._item("a1"), self._item("b2")],
            praise=[self._item("")],
            reason="test reason",
            summary="test summary",
            model_used="test model",
        )

        result = ReviewItemFactory.ensure_unique_ids(review)

        all_items = result.items + result.suggestions + result.praise
        assert all(item.id for item in all_items)
        assert len({item.id for item in all_items}) == len(all_items)

    def test_preserves_existing_unique_id(self) -> None:
        """A unique, truthy id is left untouched."""
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            items=[self._item("b2")],
            reason="test reason",
            summary="test summary",
            model_used="test model",
        )

        result = ReviewItemFactory.ensure_unique_ids(review)

        assert result.items[0].id == "b2"

