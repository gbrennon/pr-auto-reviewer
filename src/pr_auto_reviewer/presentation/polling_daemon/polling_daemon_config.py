"""PollingDaemonConfig - configuration for the polling daemon."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PollingDaemonConfig:
    """Configuration for the polling daemon."""

    poll_interval_seconds: int
    repos_filter: Optional[str]
    run_once: bool