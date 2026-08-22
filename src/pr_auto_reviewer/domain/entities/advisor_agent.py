"""AdvisorAgent — remembers focus and sends feedback to peer sub-agents."""

from __future__ import annotations

from .sub_agent import SubAgent


class AdvisorAgent(SubAgent):
    """Advisor sub-agent.

    Watches every peer sub-agent as it reviews and keeps it centered on
    its assigned responsibility. When a peer drifts — reviews the wrong
    scope, glosses over evidence, or stops exploring — the advisor
    interrupts with a grade and re-sends an improved, focused prompt.

    Grades follow a school-letter scale:
    - ``impressive`` (S) when the peer exceeded its focus.
    - ``okok`` (B) when the peer stayed on task.
    - ``whatever`` (D) when the peer drifted.
    - ``don't do this!`` (F) when the peer acted against its task; the
      advisor then blocks the output and restarts with a clarified prompt.
    """

    @property
    def role(self) -> str:
        """Return the agent's role name."""
        return "advisor"

    @property
    def responsibility(self) -> str:
        """Return the agent's responsibility statement."""
        return (
            "prevent other sub agents from being side-tracked and "
            "keep every phase focused on its assigned task"
        )

    @property
    def behavior(self) -> str:
        """Return the agent's behavior description."""
        return (
            "watch sub agents actions, grade them on focus, interrupt "
            "drift with feedback, and resend the original prompt when a "
            "sub agent goes off-task"
        )

    @property
    def interaction(self) -> str:
        """Return how the agent interacts with peer sub-agents."""
        return (
            "interrupts other sub agents to remind them of their task; "
            "grades: impressive (S), okok (B), whatever (D), "
            "don't do this! (F) — blocking and re-prompting on F"
        )

    @property
    def description(self) -> str:
        """Return a longer human-readable description."""
        return (
            "The advisor is a mix of a coach and a hall monitor. It does "
            "not review code itself: it watches what each peer sub-agent "
            "is doing, remembers each one's responsibility, and grades "
            "every action. On an F it tells the peer \"don't do this!\", "
            "blocks the output, and restarts the phase with an improved "
            "version of the original prompt that explains the task again."
        )