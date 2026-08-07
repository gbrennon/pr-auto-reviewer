"""ReviewPhase — a single phase in a multi-phase review plan."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewPhase:
    """One phase of a multi-phase code review.

    Each phase has a unique identifier, a human-readable name, and a
    system prompt that guides the LLM's behavior during that phase.
    """

    phase_id: str
    phase_name: str
    system_prompt: str
