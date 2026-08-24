"""AdvisorGranularity — when the advisor grades the peer sub-agent."""

from __future__ import annotations

from enum import Enum


class AdvisorGranularity(str, Enum):
    """Selects whether the advisor grades every turn or only whole phases."""

    TURN = "turn"
    PHASE = "phase"

    @classmethod
    def parse(cls, value: str | None) -> AdvisorGranularity:
        """Parse a raw config value, raising ValueError when unrecognized."""
        if isinstance(value, cls):
            return value
        normalized = (value or "").strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(
            f"ADVISOR_GRANULARITY must be one of "
            f"{[m.value for m in cls]}, got {value!r}"
        )
