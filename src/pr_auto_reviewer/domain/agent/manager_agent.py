"""ManagerAgent — orchestrates sub-agents in the review workflow."""

from __future__ import annotations

from pr_auto_reviewer.domain.agent.sub_agent import SubAgent


class ManagerAgent(SubAgent):
    """Manager sub-agent.

    Orchestrates the sub-agents in the review workflow, communicating
    with them and tracking their work.
    """

    @property
    def role(self) -> str:
        """Return the agent's role name."""
        return "manager"

    @property
    def responsibility(self) -> str:
        """Return the agent's responsibility statement."""
        return "orchestrate sub agents in the review workflow"

    @property
    def behavior(self) -> str:
        """Return the agent's behavior description."""
        return "communicate and track other sub agents work"