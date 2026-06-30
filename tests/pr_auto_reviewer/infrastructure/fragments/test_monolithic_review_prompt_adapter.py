"""Tests for MonolithicReviewPromptAdapter."""

from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext
from pr_auto_reviewer.infrastructure.fragments.monolithic_review_prompt_adapter import (
    MonolithicReviewPromptAdapter,
)


class TestMonolithicReviewPromptAdapter:
    def test_truncates_diff_to_fit_budget(self):
        """Diff is truncated when it exceeds budget."""
        adapter = MonolithicReviewPromptAdapter(max_total_chars=500)
        big_diff = "x" * 1000
        context = ReviewContext(
            language="python",
            file_paths=["a.py"],
            diff=big_diff,
            repository_context="",
        )
        result = adapter.execute(context)
        assert "diff omitted" in result.content
        assert "```diff" in result.content

    def test_small_diff_fits_without_truncation(self):
        adapter = MonolithicReviewPromptAdapter(max_total_chars=5000)
        context = ReviewContext(
            language="python",
            file_paths=["a.py"],
            diff="-old\n+new\n",
            repository_context="context",
        )
        result = adapter.execute(context)
        assert "-old" in result.content
        assert "truncated" not in result.content.lower()
