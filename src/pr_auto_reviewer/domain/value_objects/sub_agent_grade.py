"""SubAgentGrade — the advisor's school-letter grade for a peer phase."""

from __future__ import annotations

from enum import StrEnum
from pr_auto_reviewer.domain.exceptions.llm_response_malformed_error import (
    LlmResponseMalformedError,
)


class SubAgentGrade(StrEnum):
    """The advisor's school-letter grade for a finished peer phase.

    Mirrors the documented advisor scale, highest to lowest:
    - ``IMPRESSIVE`` — S: exceeded focus; outstanding turn.
    - ``AMAZING`` — A: real, grounded progress worth acknowledging.
    - ``OKOK`` — B: stayed on task.
    - ``ACCEPTABLE`` — C: met the minimum of the task, nothing more.
    - ``WHATEVER`` — D: drifted.
    - ``DONT_DO_THIS`` — F: acted against its task; the output is
      blocked and handed back through the manager.
    """

    IMPRESSIVE = "impressive"
    AMAZING = "amazing"
    OKOK = "okok"
    ACCEPTABLE = "acceptable"
    WHATEVER = "whatever"
    DONT_DO_THIS = "don't do this!"

    @classmethod
    def from_phrase(cls, phrase: str) -> SubAgentGrade:
        """Return the grade matching a supplied grade phrase."""
        try:
            return cls(phrase.strip().lower())
        except (AttributeError, ValueError) as exc:
            raise LlmResponseMalformedError(str(phrase)) from exc

    @property
    def blocks(self) -> bool:
        """Return whether this grade blocks the phase output and re-prompts."""
        return self is SubAgentGrade.DONT_DO_THIS