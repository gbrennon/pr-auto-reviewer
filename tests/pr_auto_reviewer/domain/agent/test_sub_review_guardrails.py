"""Tests for SubReviewGuardrails verdict-from-findings policy."""

from __future__ import annotations

from pr_auto_reviewer.domain.agent.sub_review_guardrails import (
    SubReviewGuardrails,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


class TestVerdictFor:
    """Verdict derivation from the blocking status of a sub-review's findings."""

    @staticmethod
    def _item(severity: ItemSeverity, category: IssueCategory) -> ReviewItem:
        return ReviewItem(
            number=1,
            severity=severity,
            category=category,
            file_path="src/a.py",
            description="finding",
            line="42",
        )

    def test_empty_items_imply_approval(self) -> None:
        guardrails = SubReviewGuardrails()
        assert guardrails.verdict_for([]) is ReviewVerdict.APPROVED

    def test_blocking_item_requests_changes(self) -> None:
        guardrails = SubReviewGuardrails()
        items = [self._item(ItemSeverity.MAJOR, IssueCategory.BUG)]
        assert guardrails.verdict_for(items) is ReviewVerdict.CHANGES_REQUESTED

    def test_non_blocking_items_imply_approval(self) -> None:
        guardrails = SubReviewGuardrails()
        items = [self._item(ItemSeverity.MINOR, IssueCategory.BUG)]
        assert guardrails.verdict_for(items) is ReviewVerdict.APPROVED


class TestIsCoherent:
    """Verdict-vs-findings coherence checks."""

    @staticmethod
    def _item(severity: ItemSeverity, category: IssueCategory) -> ReviewItem:
        return ReviewItem(
            number=1,
            severity=severity,
            category=category,
            file_path="src/a.py",
            description="finding",
            line="42",
        )

    def test_approval_is_coherent_without_blocking(self) -> None:
        guardrails = SubReviewGuardrails()
        items = [self._item(ItemSeverity.MINOR, IssueCategory.BUG)]
        assert guardrails.is_coherent(ReviewVerdict.APPROVED, items) is True

    def test_change_request_is_coherent_with_blocking(self) -> None:
        guardrails = SubReviewGuardrails()
        items = [self._item(ItemSeverity.MAJOR, IssueCategory.BUG)]
        assert (
            guardrails.is_coherent(ReviewVerdict.CHANGES_REQUESTED, items)
            is True
        )

    def test_approval_is_incoherent_with_blocking(self) -> None:
        guardrails = SubReviewGuardrails()
        items = [self._item(ItemSeverity.MAJOR, IssueCategory.BUG)]
        assert guardrails.is_coherent(ReviewVerdict.APPROVED, items) is False

    def test_change_request_is_incoherent_without_blocking(self) -> None:
        guardrails = SubReviewGuardrails()
        items = [self._item(ItemSeverity.MINOR, IssueCategory.BUG)]
        assert (
            guardrails.is_coherent(ReviewVerdict.CHANGES_REQUESTED, items)
            is False
        )


class TestReconcile:
    """Verdict reconciliation preserving coherent verdicts."""

    @staticmethod
    def _item(severity: ItemSeverity, category: IssueCategory) -> ReviewItem:
        return ReviewItem(
            number=1,
            severity=severity,
            category=category,
            file_path="src/a.py",
            description="finding",
            line="42",
        )

    def test_preserves_coherent_verdict(self) -> None:
        guardrails = SubReviewGuardrails()
        items = [self._item(ItemSeverity.MAJOR, IssueCategory.BUG)]
        assert (
            guardrails.reconcile(ReviewVerdict.CHANGES_REQUESTED, items)
            is ReviewVerdict.CHANGES_REQUESTED
        )

    def test_corrects_approval_alongside_blocking_finding(self) -> None:
        guardrails = SubReviewGuardrails()
        items = [self._item(ItemSeverity.MAJOR, IssueCategory.BUG)]
        assert (
            guardrails.reconcile(ReviewVerdict.APPROVED, items)
            is ReviewVerdict.CHANGES_REQUESTED
        )

    def test_corrects_change_request_without_blocking_finding(self) -> None:
        guardrails = SubReviewGuardrails()
        items = [self._item(ItemSeverity.MINOR, IssueCategory.BUG)]
        assert (
            guardrails.reconcile(ReviewVerdict.CHANGES_REQUESTED, items)
            is ReviewVerdict.APPROVED
        )
