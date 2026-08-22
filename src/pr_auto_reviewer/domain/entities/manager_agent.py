"""ManagerAgent — orchestrates sub-agents in the review workflow."""

from __future__ import annotations

from .sub_agent import SubAgent


class ManagerAgent(SubAgent):
    """Manager sub-agent.

    Acts like a mix of engineering manager, product manager, and CTO:
    plans and separates the review into tasks, assigns each task to a
    sub-agent, and owns the technical knowledge so peers never review a
    pull request poorly. Acts at the start of the review and between
    phases, and hands the advisor requirements and acceptance criteria.
    """

    @property
    def role(self) -> str:
        """Return the agent's role name."""
        return "manager"

    @property
    def responsibility(self) -> str:
        """Return the agent's responsibility statement."""
        return (
            "plan and separate tasks, assign them to sub agents like a "
            "software development team, and explain requirements and "
            "acceptance criteria to the advisor"
        )

    @property
    def behavior(self) -> str:
        """Return the agent's behavior description."""
        return (
            "assign refined tasks to sub agents, act at the start of the "
            "review and between phases, and own the technical context so "
            "sub agents never review the PR poorly"
        )

    @property
    def interaction(self) -> str:
        """Return how the agent interacts with peer sub-agents."""
        return (
            "works at review start and between phases; assigns each phase "
            "to a sub-agent and briefs the advisor on requirements and "
            "acceptance criteria"
        )

    @property
    def description(self) -> str:
        """Return a longer human-readable description."""
        return (
            "The manager plans the review like a delivery: it breaks the "
            "diff into focused tasks, hands each task to the right peer, "
            "and keeps the technical bar high so no phase rubber-stamps "
            "the changes. It also translates the PR intent into clear "
            "requirements for the advisor before phases start."
        )
