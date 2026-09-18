"""Tests for CompactionPolicy."""

import pytest

from pr_auto_reviewer.domain.value_objects.compaction_policy import CompactionPolicy


class TestCompactionPolicy:
    """Compaction policy defaults and validation."""

    def test_has_expected_defaults(self) -> None:
        policy = CompactionPolicy()

        assert policy.preserve_recent_messages == 4
        assert policy.target_utilization_ratio == 0.5
        assert policy.chars_per_token == 4.0

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"preserve_recent_messages": 0},
            {"target_utilization_ratio": 0.0},
            {"target_utilization_ratio": 1.1},
            {"chars_per_token": 0.0},
        ],
    )
    def test_rejects_invalid_values(self, kwargs: dict[str, object]) -> None:
        with pytest.raises(ValueError):
            CompactionPolicy(**kwargs)
