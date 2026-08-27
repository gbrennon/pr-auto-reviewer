"""Tests for _PhaseRunOutcome value object."""

from __future__ import annotations

from pr_auto_reviewer.application.services.multi_phase_review_orchestrator_service.phase_run_outcome import (
    _PhaseRunOutcome,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


class TestPhaseRunOutcome:
    """Validate behavior and property accessors on _PhaseRunOutcome."""

    @staticmethod
    def _create_review(items: tuple[ReviewItem, ...] = ()) -> CodeReview:
        """Create a CodeReview for testing."""
        return CodeReview(
            verdict=ReviewVerdict.APPROVED.value,
            reason="All checks passed.",
            summary="Clean review.",
            items=list(items),
            model_used="test-model",
        )

    @staticmethod
    def _create_item(file_path: str = "src/main.py") -> ReviewItem:
        """Create a single ReviewItem for testing."""
        return ReviewItem(
            file_path=file_path,
            line="10",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            description="Sample issue.",
        )
    def test_is_clean_refutation_when_zero_items_and_dropped_findings_then_returns_true(
        self,
    ) -> None:
        outcome = _PhaseRunOutcome(
            review=self._create_review(items=()),
            dropped_findings=3,
        )

        assert outcome.is_clean_refutation is True

    def test_is_clean_refutation_when_zero_items_and_zero_dropped_then_returns_false(
        self,
    ) -> None:
        outcome = _PhaseRunOutcome(
            review=self._create_review(items=()),
            dropped_findings=0,
        )

        assert outcome.is_clean_refutation is False

    def test_is_clean_refutation_when_has_items_and_dropped_findings_then_returns_false(
        self,
    ) -> None:
        item = self._create_item()
        outcome = _PhaseRunOutcome(
            review=self._create_review(items=(item,)),
            dropped_findings=2,
        )

        assert outcome.is_clean_refutation is False

    def test_has_items_when_items_present_then_returns_true(self) -> None:
        item = self._create_item()
        outcome = _PhaseRunOutcome(
            review=self._create_review(items=(item,)),
            dropped_findings=0,
        )

        assert outcome.has_items is True

    def test_has_items_when_empty_then_returns_false(self) -> None:
        outcome = _PhaseRunOutcome(
            review=self._create_review(items=()),
            dropped_findings=0,
        )

        assert outcome.has_items is False
