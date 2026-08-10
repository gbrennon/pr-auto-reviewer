"""ExplorerAgent — prepares the local clone for peer sub-agents."""

from __future__ import annotations

from pr_auto_reviewer.domain.agent.sub_agent import SubAgent


class ExplorerAgent(SubAgent):
    """Explorer sub-agent.

    Prepares a local clone so other sub-agents can review the diff
    directly, installing application dependencies and setting up the
    pull request for the next sub-agent to review.
    """

    @property
    def role(self) -> str:
        """Return the agent's role name."""
        return "explorer"

    @property
    def responsibility(self) -> str:
        """Return the agent's responsibility statement."""
        return (
            "prepare local clone to other sub agents can just review "
            "diff by installing and setting it up"
        )

    @property
    def behavior(self) -> str:
        """Return the agent's behavior description."""
        return (
            "install application dependencies based in instructions "
            "(like md files) and setup pr to next sub agent review"
        )