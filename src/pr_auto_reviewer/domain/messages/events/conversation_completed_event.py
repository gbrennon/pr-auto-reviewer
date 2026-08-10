"""ConversationCompletedEvent — emitted when an agent conversation phase finishes."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.agent.phase_result import PhaseResult


@dataclass(frozen=True)
class ConversationCompletedEvent:
    """Emitted when a single-phase agent conversation reaches a verdict."""

    phase_result: PhaseResult
