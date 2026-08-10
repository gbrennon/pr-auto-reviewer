"""AdvisorAgent — remembers focus and sends feedback to peer sub-agents."""

from __future__ import annotations

from pr_auto_reviewer.domain.agent.sub_agent import SubAgent


class AdvisorAgent(SubAgent):
    """Advisor sub-agent.

    Remembers the focus of tasks while interacting with other sub-agents
    and keeps them aligned on what they should be concentrating on.
    """

    @property
    def role(self) -> str:
        """Return the agent's role name."""
        return "advisor"

    @property
    def responsibility(self) -> str:
        """Return the agent's responsibility statement."""
        return "remember focus of tasks interacting with other sub agents"

    @property
    def behavior(self) -> str:
        """Return the agent's behavior description."""
        return (
            "send message to other sub agents with feedback, prose and "
            "remind agents what they should focus"
        )