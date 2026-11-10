"""ActiveReviewProgress — snapshot of in-flight review execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActiveReviewProgress:
    """Carries progress details for a currently active pull request review."""

    repository: str
    pr_number: int
    pr_title: str
    head_sha: str
    started_at: str
    phase_name: str = ""
    phase_index: int = 0
    total_phases: int = 0
    subagent_role: str = ""
    current_turn: int = 0
    max_turns: int = 0
    last_tool_call: str = ""
    last_tool_args: str = ""
