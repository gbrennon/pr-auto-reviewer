"""Tests for PraiseRegressionPolicy domain service."""

from __future__ import annotations

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.services.praise_regression_policy import (
    PraiseRegressionPolicy,
)
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity


class TestPraiseRegressionPolicy:
    """Deterministic detection of praise the current review no longer affirms."""

    @staticmethod
    def _praise(description: str, file_path: str = "src/auth.py") -> ReviewItem:
        return ReviewItem(
            severity=ItemSeverity.INFO,
            category=IssueCategory.GENERAL,
            file_path=file_path,
            description=description,
        )

    def test_affirmed_praise_produces_no_regression(self) -> None:
        policy = PraiseRegressionPolicy()
        prior = [self._praise("Thorough input validation")]
        current = [self._praise("Thorough input validation")]
        assert policy.regressions(prior, current, []) == []

    def test_lost_praise_becomes_a_suggestion(self) -> None:
        policy = PraiseRegressionPolicy()
        prior = [self._praise("Thorough input validation")]
        regressions = policy.regressions(prior, [], [])
        assert len(regressions) == 1
        suggestion = regressions[0]
        assert suggestion.severity == ItemSeverity.INFO
        assert suggestion.category == IssueCategory.GENERAL
        assert suggestion.file_path == "src/auth.py"
        assert "Thorough input validation" in suggestion.description
        assert "no longer present" in suggestion.description

    def test_regression_is_never_blocking(self) -> None:
        policy = PraiseRegressionPolicy()
        prior = [self._praise("Clear separation of concerns")]
        assert policy.regressions(prior, [], [])[0].is_blocking is False

    def test_match_is_case_insensitive_and_path_scoped(self) -> None:
        policy = PraiseRegressionPolicy()
        prior = [self._praise("Thorough Input Validation")]
        current = [self._praise("thorough input validation")]
        assert policy.regressions(prior, current, []) == []

    def test_same_quality_on_different_file_is_still_lost(self) -> None:
        policy = PraiseRegressionPolicy()
        prior = [self._praise("Thorough input validation", "src/a.py")]
        current = [self._praise("Thorough input validation", "src/b.py")]
        assert len(policy.regressions(prior, current, [])) == 1

    def test_duplicate_prior_praise_yields_one_regression(self) -> None:
        policy = PraiseRegressionPolicy()
        prior = [
            self._praise("Thorough input validation"),
            self._praise("Thorough input validation"),
        ]
        assert len(policy.regressions(prior, [], [])) == 1

    def test_already_suggested_regression_is_not_restated(self) -> None:
        policy = PraiseRegressionPolicy()
        prior = [self._praise("Thorough input validation")]
        first = policy.regressions(prior, [], [])
        assert len(first) == 1
        second = policy.regressions(prior, [], first)
        assert second == []
