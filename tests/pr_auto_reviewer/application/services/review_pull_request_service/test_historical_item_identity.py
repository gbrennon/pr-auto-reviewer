from ._helpers import *
from dataclasses import replace
from pr_auto_reviewer.domain.value_objects.review_audit_result import ReviewAuditResult
from pr_auto_reviewer.domain.value_objects.review_item_status import ReviewItemStatus


class TestHistoricalItemIdentity:
    """Historical review records are deduplicated only by stable identity."""

    @staticmethod
    def _item(
        item_id: str,
        code: str,
        description: str = "Finding",
    ) -> ReviewItem:
        return ReviewItem(
            id=item_id,
            severity=ItemSeverity.MINOR,
            category=IssueCategory.MAINTAINABILITY,
            file_path="src/mod.py",
            description=description,
            current_code=code,
        )

    @staticmethod
    def _review_with_items(*items: ReviewItem) -> CodeReview:
        return CodeReview(
            verdict=ReviewVerdict.APPROVED,
            items=list(items),
            summary="Review",
            model_used="test",
            reason="test reason",
        )

    def test_repeated_identity_is_projected_once(self) -> None:
        first = self._item("item-1", "y = unsafe(x)")
        repeated = self._item("item-1", "y = safe(x)")
        pr = _pr(_pr_id(), _sha("old111")).add_review(
            self._review_with_items(first), _sha("old111")
        ).add_review(
            self._review_with_items(repeated), _sha("new222")
        )

        history = pr.historical_items()

        assert [item.id for item in history] == ["item-1"]

    def test_distinct_identity_on_same_file_survives(self) -> None:
        first = self._item("item-1", "y = unsafe(x)")
        second = self._item("item-2", "y = other_problem()")
        pr = _pr(_pr_id(), _sha()).add_review(
            self._review_with_items(first, second), _sha()
        )

        history = pr.historical_items()

        assert [item.id for item in history] == ["item-1", "item-2"]

    def test_whitespace_variation_with_distinct_identity_survives(self) -> None:
        first = self._item("item-1", "y   =  unsafe(x)\n")
        second = self._item("item-2", "y = unsafe(x)")
        pr = _pr(_pr_id(), _sha()).add_review(
            self._review_with_items(first, second), _sha()
        )

        history = pr.historical_items()

        assert [item.id for item in history] == ["item-1", "item-2"]

    def test_distinct_empty_code_records_survive(self) -> None:
        first = self._item("item-1", "", "Missing class docstring")
        second = self._item("item-2", "", "Unused import os")
        pr = _pr(_pr_id(), _sha()).add_review(
            self._review_with_items(first, second), _sha()
        )

        history = pr.historical_items()

        assert [item.description for item in history] == [
            "Missing class docstring",
            "Unused import os",
        ]

    def test_repeated_empty_code_identity_is_projected_once(self) -> None:
        first = self._item("item-1", "", "Missing class docstring")
        repeated = self._item("item-1", "", "Missing class docstring")
        pr = _pr(_pr_id(), _sha()).add_review(
            self._review_with_items(first), _sha()
        ).add_review(
            self._review_with_items(repeated), _sha("new222")
        )

        history = pr.historical_items()

        assert [item.id for item in history] == ["item-1"]

    def test_new_pull_request_has_no_historical_records(self) -> None:
        pr = _pr(_pr_id(), _sha())

        history = pr.historical_items()

        assert history == ()

    def test_terminal_recurrence_receives_a_new_identity(self) -> None:
        service = ReviewPullRequestService(
            MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(),
        )
        terminal = self._item("item-1", "y = unsafe(x)")
        terminal = replace(terminal, status=ReviewItemStatus.RESOLVED)
        recurrence = self._item("item-1", "y = unsafe(x)")
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            items=[recurrence],
            summary="Review",
            model_used="test",
            reason="test reason",
        )

        merged = service._merge_audited_history(
            review,
            ReviewAuditResult(items=(terminal,)),
            frozenset(),
            review_contains_audit=True,
        )

        assert [item.id for item in merged.items] == ["item-1", merged.items[1].id]
        assert merged.items[1].id != "item-1"
