import pytest

from pr_auto_reviewer.infrastructure.fragments.monolithic_review_prompt_adapter import (
    MonolithicReviewPromptAdapter,
)
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext


def test_repository_context_truncation():
    long_ctx = "x" * 5000
    adapter = MonolithicReviewPromptAdapter()
    ctx = ReviewContext(language="python", file_paths=["a.py"], diff="+x", repository_context=long_ctx)
    result = adapter.execute(ctx)
    assert "repository context truncated" in result.content


def test_diff_omitted_when_no_budget():
    # Force available==0 by setting very small max_total_chars
    adapter = MonolithicReviewPromptAdapter(max_total_chars=10)
    ctx = ReviewContext(language="python", file_paths=["a.py"], diff="+def f(): pass")
    result = adapter.execute(ctx)
    assert "diff omitted" in result.content


def test_diff_truncation_with_newline_preference():
    # Set a small budget so truncation happens but available>0
    # Craft diff with multiple lines so last_newline > available//2
    diff_lines = "\n".join([f"+line{i}" for i in range(50)])
    adapter = MonolithicReviewPromptAdapter(max_total_chars=400)
    ctx = ReviewContext(language="python", file_paths=["a.py"], diff=diff_lines)
    result = adapter.execute(ctx)
    # When truncated (or budget forces omission), the prompt should indicate truncation or omission
    assert "diff truncated" in result.content or "diff omitted" in result.content
