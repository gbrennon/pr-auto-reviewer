"""Tests for RetryPromptBuilder using captured fixtures."""

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.response_normalizer import RetryPromptBuilder
from tests.fixtures.response_normalizer_fixtures import ResponseNormalizerFixtures as F


class TestRetryPromptBuilder:
    def test_build_correction_prompt_single_failure(self):
        builder = RetryPromptBuilder()
        result = builder.build_correction_prompt(
            "original prompt", F.retry_failures_single
        )
        assert "original prompt" in result
        assert len(result) > len("original prompt")

    def test_build_correction_prompt_multiple_failures(self):
        builder = RetryPromptBuilder()
        result = builder.build_correction_prompt("prompt", F.retry_failures_multiple)
        assert "prompt" in result

    def test_build_correction_prompt_unknown_failure(self):
        builder = RetryPromptBuilder()
        result = builder.build_correction_prompt("prompt", F.retry_failures_unknown)
        assert isinstance(result, str)

    def test_diagnose_failures_commented_verdict(self):
        builder = RetryPromptBuilder()
        review = CodeReview(
            verdict=ReviewVerdict.COMMENTED, summary="s", items=[], model_used="m",
        )
        failures = builder.diagnose_failures(review)
        assert any("verdict is missing or unclear" in f for f in failures)

    def test_diagnose_failures_approved_with_summary_no_items(self):
        builder = RetryPromptBuilder()
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED, summary="s", items=[], model_used="m",
        )
        failures = builder.diagnose_failures(review)
        assert not any("no review items found" in f for f in failures)

    def test_diagnose_failures_approved_no_summary_no_items(self):
        builder = RetryPromptBuilder()
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED, summary="", items=[], model_used="m",
        )
        failures = builder.diagnose_failures(review)
        assert any("no review items found" in f for f in failures)

    def test_diagnose_failures_missing_description(self):
        builder = RetryPromptBuilder()
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED, summary="s",
            items=[ReviewItem(number=1, severity=ItemSeverity.MINOR, category="bug",
                              description="", file_path="f.py", current_code="c", suggested_fix="x")],
            model_used="m",
        )
        failures = builder.diagnose_failures(review)
        assert any("missing 'description'" in f for f in failures)

    def test_diagnose_failures_missing_current_code(self):
        builder = RetryPromptBuilder()
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED, summary="s",
            items=[ReviewItem(number=1, severity=ItemSeverity.MINOR, category="bug",
                              description="d", file_path="f.py", current_code="", suggested_fix="x")],
            model_used="m",
        )
        failures = builder.diagnose_failures(review)
        assert any("missing 'current_code'" in f for f in failures)

    def test_diagnose_failures_missing_suggested_fix(self):
        builder = RetryPromptBuilder()
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED, summary="s",
            items=[ReviewItem(number=1, severity=ItemSeverity.MINOR, category="bug",
                              description="d", file_path="f.py", current_code="c", suggested_fix="")],
            model_used="m",
        )
        failures = builder.diagnose_failures(review)
        assert any("missing 'suggested_fix'" in f for f in failures)

    def test_diagnose_failures_missing_file(self):
        builder = RetryPromptBuilder()
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED, summary="s",
            items=[ReviewItem(number=1, severity=ItemSeverity.MINOR, category="bug",
                              description="d", file_path="", current_code="c", suggested_fix="x")],
            model_used="m",
        )
        failures = builder.diagnose_failures(review)
        assert any("missing 'file'" in f for f in failures)

    def test_diagnose_failures_all_ok(self):
        builder = RetryPromptBuilder()
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED, summary="s",
            items=[ReviewItem(number=1, severity=ItemSeverity.MINOR, category="bug",
                              description="d", file_path="f.py", current_code="c", suggested_fix="x")],
            model_used="m",
        )
        failures = builder.diagnose_failures(review)
        assert failures == []
