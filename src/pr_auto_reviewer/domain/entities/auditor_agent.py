"""AuditorAgent — proves whether prior findings were remediated."""

from __future__ import annotations

from .sub_agent import SubAgent


class AuditorAgent(SubAgent):
    """Auditor sub-agent.

    Re-reviews a file that was reviewed before and has since changed,
    deciding for each prior finding whether the defect is provably gone.
    """

    @property
    def role(self) -> str:
        """Return the agent's role name."""
        return "auditor"

    @property
    def responsibility(self) -> str:
        """Return the agent's responsibility statement."""
        return (
            "re-review files that were reviewed before and have changed; "
            "for each prior finding, prove the defect is gone before "
            "marking it resolved, and leave it open otherwise"
        )

    @property
    def behavior(self) -> str:
        """Return the agent's behavior description."""
        return (
            "read the updated file and the diff; re-run the finding's "
            "detection method and reproduction; mark resolved only when "
            "acceptance criteria are met and reproduction no longer "
            "triggers; never resolve a finding by absence of evidence"
        )

    @property
    def interaction(self) -> str:
        """Return how the agent interacts with peer sub-agents."""
        return (
            "owns the open/resolved decision for prior findings; does "
            "not re-review new findings, which the verifier fact-checks"
        )

    @property
    def description(self) -> str:
        """Return a longer human-readable description."""
        return (
            "The auditor revisits each previously reported finding on a "
            "file that changed. It reproduces the original defect using "
            "the recorded detection method and reproduction steps, then "
            "checks the acceptance criteria against the updated code. A "
            "finding becomes resolved only with positive proof; anything "
            "it cannot establish stays open."
        )
