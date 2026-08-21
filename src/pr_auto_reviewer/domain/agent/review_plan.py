"""ReviewPlan — the ordered sequence of phases for a multi-phase review."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.agent.review_phase import ReviewPhase


@dataclass(frozen=True)
class ReviewPlan:
    """A complete multi-phase review plan.

    Carries the ordered sequence of phases and the anti-hallucination
    methodology rules injected into every phase prompt. When
    ``suggestions_phase_id`` names one of the phases, that phase's
    ``llm_suggestions`` are the sole source of the final review's
    ``suggestions``; when unset, the last phase's suggestions are used.
    An optional ``manager_brief`` is prepended to the first phase so the
    manager role opens the review with task assignment and acceptance
    criteria.
    """

    phases: tuple[ReviewPhase, ...]
    methodology: str
    suggestions_phase_id: str | None = None
    manager_brief: str = ""
