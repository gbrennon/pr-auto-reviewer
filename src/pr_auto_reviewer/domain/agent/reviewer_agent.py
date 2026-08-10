"""ReviewerAgent — joins sub-agent outputs into the final verdict."""

from __future__ import annotations

from pr_auto_reviewer.domain.agent.sub_agent import SubAgent


class ReviewerAgent(SubAgent):
    """Reviewer sub-agent.

    Joins the review output of the other sub-agents and produces the
    final verdict and output by reading their results and preparing the
    final turn verdict.
    """

    @property
    def role(self) -> str:
        """Return the agent's role name."""
        return "reviewer"

    @property
    def responsibility(self) -> str:
        """Return the agent's responsibility statement."""
        return (
            "join review output of sub agents and so the final verdict "
            "and output"
        )

    @property
    def behavior(self) -> str:
        """Return the agent's behavior description."""
        return (
            "read output of other sub agents and prepare the final "
            "turn verdict"
        )