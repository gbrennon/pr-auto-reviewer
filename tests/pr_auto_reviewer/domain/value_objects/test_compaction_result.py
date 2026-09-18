"""Tests for CompactionResult."""

from pr_auto_reviewer.domain.value_objects.compaction_result import CompactionResult
from pr_auto_reviewer.domain.value_objects.token_count import TokenCount


class TestCompactionResult:
    """Compaction result calculations."""

    def test_calculates_freed_tokens_and_removed_messages(self) -> None:
        result = CompactionResult(
            original_tokens=TokenCount(100),
            compacted_tokens=TokenCount(40),
            messages_before=10,
            messages_after=5,
            summary="summary",
        )

        assert result.tokens_freed == TokenCount(60)
        assert result.compression_ratio == 0.4
        assert result.messages_removed == 5
        assert result.did_compact
