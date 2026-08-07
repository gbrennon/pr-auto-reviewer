"""RunMultiPhaseReviewCommand — input for running a multi-phase review plan."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.agent.review_plan import ReviewPlan


@dataclass(frozen=True)
class RunMultiPhaseReviewCommand:
    """Command to execute a full multi-phase review plan against a repository."""

    plan: ReviewPlan
    repo_path: str
    changed_files: list[str]
    model: str
