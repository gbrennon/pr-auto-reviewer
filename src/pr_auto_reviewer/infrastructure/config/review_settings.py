"""Parsed review and runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.infrastructure.config.advisor_granularity import AdvisorGranularity


@dataclass(frozen=True)
class ReviewSettings:
    """Configuration controlling review execution and output."""

    advisor_max_blocks: int
    review_max_conversations: int
    review_max_retries: int
    review_max_tries: int
    advisor_granularity: AdvisorGranularity
    poll_interval: int
    run_once: bool
    debug: bool
    output_mode: str
    output_path: str | None
    max_prompt_tokens: int
    max_file_chars: int
    max_files: int
    max_structure_lines: int
    use_compact_template: bool
    use_strict_fragment_selection: bool
