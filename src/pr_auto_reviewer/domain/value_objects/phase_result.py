"""PhaseResult — items and metadata from a single review phase conversation."""

from __future__ import annotations

from dataclasses import dataclass, field

from pr_auto_reviewer.domain.entities.review_item import ReviewItem


@dataclass(frozen=True)
class PhaseResult:
    """Items and metadata from a single review phase conversation.

    Carries LLM-extracted verdict, reason, summary, suggestions, and
    praise alongside the validated ReviewItem list so downstream code
    can populate every CodeReview field.
    """

    items: list[ReviewItem] = field(default_factory=list)
    llm_verdict: str | None = None
    llm_reason: str = ""
    llm_summary: str = ""
    llm_suggestions: list[dict[str, str]] = field(default_factory=list)
    llm_praise: list[dict[str, str]] = field(default_factory=list)
    turn_count: int = 0
    read_file_calls: int = 0
    run_snippet_calls: int = 0
    skip_reasons: list[str] = field(default_factory=list)
