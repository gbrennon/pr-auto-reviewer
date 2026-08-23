"""BriefNextPhaseUseCase — the manager assigns the task for the next phase."""

from __future__ import annotations

from typing import Protocol

from pr_auto_reviewer.domain.value_objects.review_phase import ReviewPhase


class BriefNextPhaseUseCase(Protocol):
    """Produce a focused task assignment for the upcoming phase.

    The manager acts at the start of the review and between phases:
    it reads the findings the completed phases produced and refines the
    task for the next phase so no peer re-reviews what another phase
    owns.
    """

    def brief(
        self,
        next_phase: ReviewPhase,
        findings_summary: str,
        pr_identifier: str = "",
    ) -> str:
        """Return the assignment text for *next_phase*, or empty when none."""
        ...