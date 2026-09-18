"""Context compaction policy value object."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CompactionPolicy:
    """Immutable policy controlling conversation compaction."""

    preserve_recent_messages: int = 4
    target_utilization_ratio: float = 0.5
    chars_per_token: float = 4.0
    summary_prefix: str = "[Context Compacted: Earlier conversation history summarized below]\n"

    def __post_init__(self) -> None:
        if self.preserve_recent_messages < 1:
            raise ValueError("preserve_recent_messages must be at least 1")
        if not 0.0 < self.target_utilization_ratio <= 1.0:
            raise ValueError("target_utilization_ratio must be in (0.0, 1.0]")
        if self.chars_per_token <= 0.0:
            raise ValueError("chars_per_token must be positive")
