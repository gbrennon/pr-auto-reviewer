from ._helpers import *


class TestContentLevelDedup:
    """Byte-equivalent findings cannot republish under fresh IDs."""

    @staticmethod
    def _item(file_path, code, item_id=""):
        return ReviewItem(
            severity=ItemSeverity.MINOR,
            category=IssueCategory.MAINTAINABILITY,
            file_path=file_path,
            description="duplicated finding text",
            id=item_id,
            current_code=code,
        )

    @staticmethod
    def _persisted_pr(items):
        pr = MagicMock()
        prior = MagicMock()
        prior.items = items
        pr.reviews = [prior]
        return pr

    def test_byte_identical_finding_is_dropped(self) -> None:
        service = self._build_service()
        published = self._item(
            "src/mod.py", "y = unsafe(x)", item_id="1a0305",
        )
        recycled = self._item(
            "src/mod.py", "y = unsafe(x)", item_id="1a0306",
        )
        review = _review(ReviewVerdict.APPROVED, items=[recycled])

        result = service._drop_persisted_duplicates(
            review, self._persisted_pr([published]),
        )

        assert result.items == []

    def test_distinct_finding_on_same_file_survives(self) -> None:
        service = self._build_service()
        published = self._item("src/mod.py", "y = unsafe(x)")
        fresh = self._item("src/mod.py", "z = other_problem()")
        review = _review(ReviewVerdict.APPROVED, items=[fresh])

        result = service._drop_persisted_duplicates(
            review, self._persisted_pr([published]),
        )

        assert len(result.items) == 1
        assert result.items[0].current_code == "z = other_problem()"

    def test_whitespace_normalized_code_still_matches(self) -> None:
        service = self._build_service()
        published = self._item(
            "src/mod.py", "y   =  unsafe(x)\n",
        )
        recycled = self._item(
            "src/mod.py", "y = unsafe(x)",
        )
        review = _review(ReviewVerdict.APPROVED, items=[recycled])

        result = service._drop_persisted_duplicates(
            review, self._persisted_pr([published]),
        )

        assert result.items == []

    def test_no_prior_reviews_returns_review_unchanged(self) -> None:
        service = self._build_service()
        review = _review(ReviewVerdict.APPROVED)

        assert (
            service._drop_persisted_duplicates(review, None) is review
        )

    @staticmethod
    def _build_service() -> ReviewPullRequestService:
        return ReviewPullRequestService(
            MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(),
        )
