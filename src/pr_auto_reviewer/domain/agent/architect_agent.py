"""ArchitectAgent — enforces architecture good practices."""

from __future__ import annotations

from pr_auto_reviewer.domain.agent.sub_agent import SubAgent


class ArchitectAgent(SubAgent):
    """Architect sub-agent.

    Enforces architecture good practices and searches for software
    architecture misses by reading source code to identify violations,
    coupling, and poor implementations.
    """

    @property
    def role(self) -> str:
        """Return the agent's role name."""
        return "architect"

    @property
    def responsibility(self) -> str:
        """Return the agent's responsibility statement."""
        return (
            "enforce architecture good practices and search for "
            "software architecture misses"
        )

    @property
    def behavior(self) -> str:
        """Return the agent's behavior description."""
        return (
            "read source code to identify misses, violations, "
            "coupling, poor implementations"
        )