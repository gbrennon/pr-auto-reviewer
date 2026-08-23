"""PhaseTurnObserver — the advisor grades each peer turn as it happens."""

from __future__ import annotations

from typing import Protocol

from pr_auto_reviewer.domain.value_objects.advisor_directive import (
    AdvisorDirective,
)


class PhaseTurnObserver(Protocol):
    """Watch a peer conversation turn-by-turn and interrupt drift early.

    Unlike the post-phase grading in
    ``AssessPhaseUseCase``, this contract observes every raw peer turn
    while the conversation is still running, so a drifting sub-agent is
    corrected mid-flight instead of after its output is complete.
    """

    def observe(
        self,
        peer_content: str,
        phase_name: str,
        pr_identifier: str = "",
    ) -> AdvisorDirective:
        """Grade one peer turn and return the directive for it."""
        ...
