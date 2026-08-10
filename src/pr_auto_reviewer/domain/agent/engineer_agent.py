"""EngineerAgent — exercises changes searching for bugs."""

from __future__ import annotations

from pr_auto_reviewer.domain.agent.sub_agent import SubAgent


class EngineerAgent(SubAgent):
    """Engineer sub-agent.

    Exercises the changes by using modifications, reading code to search
    for software engineering misses and spawning a REPL to interact with
    the code when needed.
    """

    @property
    def role(self) -> str:
        """Return the agent's role name."""
        return "engineer"

    @property
    def responsibility(self) -> str:
        """Return the agent's responsibility statement."""
        return "exercise changes searching for bugs by using modifications"

    @property
    def behavior(self) -> str:
        """Return the agent's behavior description."""
        return (
            "read code to search for software engineering misses and "
            "it can spawn repl to exercise code"
        )