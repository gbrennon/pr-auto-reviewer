"""EngineerAgent — exercises changes searching for bugs."""

from __future__ import annotations

from pr_auto_reviewer.domain.agent.sub_agent import SubAgent


class EngineerAgent(SubAgent):
    """Engineer sub-agent.

    Acts like a principal software engineer who enjoys clean, decoupled
    code. Exercises the changes — reading code, searching for bugs,
    checking quality, test coverage, and principles — and suggests
    practices that fit what the project already does, never something
    brand new that has no precedent in the codebase.
    """

    @property
    def role(self) -> str:
        """Return the agent's role name."""
        return "engineer"

    @property
    def responsibility(self) -> str:
        """Return the agent's responsibility statement."""
        return (
            "exercise the changes searching for bugs and improvements; "
            "analyze code quality, test coverage, principles; and suggest "
            "good practices that match the project's existing approach"
        )

    @property
    def behavior(self) -> str:
        """Return the agent's behavior description."""
        return (
            "think about what the project is doing and which approach was "
            "already introduced; never suggest something extremely new; "
            "prefer clean, decoupled code"
        )

    @property
    def interaction(self) -> str:
        """Return how the agent interacts with peer sub-agents."""
        return (
            "reviews its assigned phase like a principal engineer, "
            "grounding every suggestion in the project's existing "
            "patterns and conventions"
        )

    @property
    def description(self) -> str:
        """Return a longer human-readable description."""
        return (
            "The engineer reviews the diff the way a principal would: "
            "trace the change end to end, look for bugs and missed edge "
            "cases, assess maintainability and test coverage, and only "
            "then suggest improvements. Suggestions must fit the "
            "project's established approach — a small, consistent change "
            "beats introducing a brand-new pattern."
        )