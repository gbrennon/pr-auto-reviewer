"""DaemonRuntimeStatus — immutable snapshot of daemon telemetry and review status."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.value_objects.active_review_progress import (
    ActiveReviewProgress,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState


@dataclass(frozen=True)
class DaemonRuntimeStatus:
    """Snapshot of daemon activity, configuration, and in-flight review status."""

    pid: int
    daemon_mode: bool
    state: DaemonState
    updated_at: str
    poll_interval_seconds: int
    allowed_repositories: tuple[str, ...]
    current_cycle: int = 0
    next_cycle_at: str | None = None
    current_review: ActiveReviewProgress | None = None
    last_error: str | None = None
    last_error_at: str | None = None
