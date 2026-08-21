"""ReviewPhase — a single phase in a multi-phase review plan."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.agent.sub_agent import SubAgent


@dataclass(frozen=True)
class ReviewPhase:
    """One phase of a multi-phase code review.

    Each phase has a unique identifier, a human-readable name, and a
    system prompt that guides the LLM's behavior during that phase. An
    optional ``role`` names the ``SubAgent`` executing the phase so its
    responsibility and behavior reach the composed prompt.
    """

    phase_id: str
    phase_name: str
    system_prompt: str
    role: SubAgent | None = None

    def role_brief(self) -> str:
        """Return a single-line role instruction, or empty when no role is set."""
        if self.role is None:
            return ""
        return f"Your role: {self.role.describe()}"
