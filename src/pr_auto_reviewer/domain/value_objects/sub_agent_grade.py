"""SubAgentGrade — the advisor's school-letter grade for a peer phase."""

from __future__ import annotations

from enum import StrEnum


class SubAgentGrade(StrEnum):
    """The advisor's school-letter grade for a finished peer phase.

    Mirrors the documented advisor scale:
    - ``IMPRESSIVE`` — S: the peer exceeded its focus.
    - ``OKOK`` — B: the peer stayed on task.
    - ``WHATEVER`` — D: the peer drifted.
    - ``DONT_DO_THIS`` — F: the peer acted against its task; the phase
      output is blocked and re-run with an improved prompt.
    """

    IMPRESSIVE = "impressive"
    OKOK = "okok"
    WHATEVER = "whatever"
    DONT_DO_THIS = "don't do this!"

    @classmethod
    def from_phrase(cls, phrase: str) -> SubAgentGrade:
        """Return the grade matching a grade phrase, or ``OKOK`` when unknown.

        Tolerant parse: an unrecognizable advisor response resolves to
        ``OKOK`` so an off-format reply never blocks the pipeline.
        """
        try:
            return cls(phrase.strip().lower())
        except ValueError:
            return cls.OKOK

    @property
    def blocks(self) -> bool:
        """Return whether this grade blocks the phase output and re-prompts."""
        return self is SubAgentGrade.DONT_DO_THIS