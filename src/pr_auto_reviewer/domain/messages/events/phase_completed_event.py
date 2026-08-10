"""PhaseCompletedEvent — emitted when a single review phase finishes."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.agent.phase_result import PhaseResult


@dataclass(frozen=True)
class PhaseCompletedEvent:
    """Emitted when a single review phase completes (with or without findings)."""

    phase_name: str
    phase_result: PhaseResult
    total_findings: int
