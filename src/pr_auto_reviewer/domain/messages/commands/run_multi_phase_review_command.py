"""RunMultiPhaseReviewCommand — input for running a multi-phase review plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.review_plan import ReviewPlan


@dataclass(frozen=True)
class RunMultiPhaseReviewCommand:
    """Command to execute a full multi-phase review plan against a repository."""

    plan: ReviewPlan
    repo_path: Path
    changed_files: list[str]
    model: str
    review_session: str
    """Opaque review-run key (start timestamp) grouping transcripts for one run."""
    base_sha: str = ""
    """PR merge-base against the default branch; scopes the LLM's git reads."""
    existing_item_ids: frozenset[str] = frozenset()
    prior_items: list[ReviewItem] = field(default_factory=list)
    prior_suggestions: list[ReviewItem] = field(default_factory=list)
