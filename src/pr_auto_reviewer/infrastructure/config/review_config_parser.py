"""Parse review execution configuration."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.config.advisor_granularity import AdvisorGranularity
from pr_auto_reviewer.infrastructure.config.review_settings import ReviewSettings


class ReviewConfigParser:
    """Build review and runtime settings from environment values."""

    def parse(
        self,
        source: dict[str, str],
        advisor_max_blocks: int,
        review_max_conversations: int,
        review_max_tries: int,
        granularity: AdvisorGranularity,
    ) -> ReviewSettings:
        """Parse review limits, output settings, and runtime flags."""
        output_mode = source.get("REVIEW_OUTPUT", "").strip()
        output_path: str | None = None
        if output_mode.startswith("file:"):
            output_path = output_mode.removeprefix("file:") or None
            output_mode = "terminal"
        elif not output_mode:
            output_mode = "forgejo"
        return ReviewSettings(
            advisor_max_blocks=advisor_max_blocks,
            review_max_conversations=review_max_conversations,
            review_max_tries=review_max_tries,
            advisor_granularity=granularity,
            poll_interval=int(source.get("POLL_INTERVAL", "60")),
            run_once=source.get("RUN_ONCE", "").lower() in ("true", "1", "yes"),
            debug=source.get("DEBUG", "").lower() in ("true", "1", "yes"),
            output_mode=output_mode,
            output_path=output_path,
            max_prompt_tokens=int(source.get("MAX_PROMPT_TOKENS", "9999")),
            max_file_chars=int(source.get("MAX_FILE_CHARS", "3000")),
            max_files=int(source.get("MAX_FILES", "10")),
            max_structure_lines=int(source.get("MAX_STRUCTURE_LINES", "100")),
            use_compact_template=source.get("USE_COMPACT_TEMPLATE", "").lower() == "true",
            use_strict_fragment_selection=source.get(
                "USE_STRICT_FRAGMENT_SELECTION", ""
            ).lower() == "true",
        )
