"""PollingDaemonConfig - configuration for the polling daemon."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PollingDaemonConfig:
    """Configuration for the polling daemon."""

    poll_interval_seconds: int
    repos_filter: str | None
    run_once: bool
    force_pr: int | None = None
