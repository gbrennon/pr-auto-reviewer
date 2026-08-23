"""AdvisorDirective — the advisor's grade and corrective prompt for a phase."""

from __future__ import annotations

from dataclasses import dataclass

from .sub_agent_grade import SubAgentGrade


@dataclass(frozen=True)
class AdvisorDirective:
    """The advisor's verdict on a finished phase and how to correct it.

    ``grade`` is the advisor's assessment of how the peer stayed on the
    task the manager assigned. ``feedback`` is the interjection returned
    to the peer. When ``grade`` blocks (an F), ``improved_prompt`` is the
    improved version of the original prompt that re-explains the task so
    the phase can be restarted.
    """

    grade: SubAgentGrade
    feedback: str = ""
    improved_prompt: str = ""

    @property
    def blocks_output(self) -> bool:
        """Return whether this directive blocks the phase output."""
        return self.grade.blocks