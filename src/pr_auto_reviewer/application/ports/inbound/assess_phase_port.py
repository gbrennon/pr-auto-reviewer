"""AssessPhasePort — the advisor grades a finished peer phase."""

from __future__ import annotations

from typing import Protocol

from pr_auto_reviewer.domain.value_objects.advisor_directive import (
    AdvisorDirective,
)
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.review_phase import ReviewPhase


class AssessPhasePort(Protocol):
    """Grade a finished phase and, on a blocking grade, return a corrective prompt.

    The advisor watches what the peer sub-agent did in *phase* against
    the task the manager assigned, grades every finished action on the
    S/B/D/F scale, and supplies an improved prompt when the phase must
    be restarted.
    """

    def assess(
        self,
        phase: ReviewPhase,
        assignment: str,
        phase_result: PhaseResult,
        review_session: str,
        pr_identifier_service: str = "",
    ) -> AdvisorDirective:
        """Return the advisor's directive for the finished *phase*."""
        ...