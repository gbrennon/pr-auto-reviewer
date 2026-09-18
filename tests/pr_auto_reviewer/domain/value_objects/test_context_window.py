"""Tests for ContextWindow."""

import pytest

from pr_auto_reviewer.domain.exceptions import (
    ContextWindowExceededError,
    InvalidTokenCountError,
)
from pr_auto_reviewer.domain.value_objects.context_window import ContextWindow
from pr_auto_reviewer.domain.value_objects.token_count import TokenCount


class TestContextWindow:
    """Context capacity and compaction threshold behavior."""

    def test_calculates_effective_capacity_and_available_tokens(self) -> None:
        window = ContextWindow(
            max_tokens=TokenCount(100),
            current_tokens=TokenCount(20),
            reserved_output_tokens=TokenCount(10),
        )

        assert window.effective_capacity == TokenCount(90)
        assert window.available_tokens == TokenCount(70)
        assert window.utilization == pytest.approx(20 / 90)
        assert not window.is_exhausted

    def test_can_fit_and_needs_compaction(self) -> None:
        window = ContextWindow(
            max_tokens=TokenCount(100), current_tokens=TokenCount(70)
        )

        assert window.can_fit(30)
        assert not window.can_fit(31)
        assert not window.needs_compaction()
        assert window.needs_compaction(0.7)

    def test_exhausted_window_needs_compaction(self) -> None:
        window = ContextWindow(
            max_tokens=TokenCount(100), current_tokens=TokenCount(100)
        )

        assert window.is_exhausted
        assert window.needs_compaction()
        assert window.available_tokens is TokenCount.ZERO

    def test_rejects_invalid_configuration(self) -> None:
        with pytest.raises(InvalidTokenCountError, match="positive"):
            ContextWindow(max_tokens=TokenCount.ZERO)
        with pytest.raises(ValueError, match="compact_threshold_ratio"):
            ContextWindow(max_tokens=TokenCount(10), compact_threshold_ratio=0.0)
        with pytest.raises(ContextWindowExceededError, match="strictly less"):
            ContextWindow(
                max_tokens=TokenCount(10), reserved_output_tokens=TokenCount(10)
            )

    def test_token_update_methods_return_new_windows(self) -> None:
        window = ContextWindow(max_tokens=TokenCount(100))

        updated = window.with_current_tokens(20).with_added_tokens(5)
        reserved = updated.with_reserved_output(10)

        assert updated.current_tokens == TokenCount(25)
        assert reserved.reserved_output_tokens == TokenCount(10)
        assert window.current_tokens is TokenCount.ZERO
