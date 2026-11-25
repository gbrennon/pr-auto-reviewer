from dataclasses import dataclass

from pr_auto_reviewer.application.dtos.daemon_status_snapshot import (
    DaemonStatusSnapshot,
)


@dataclass(frozen=True)
class ShowStatusResponse:
    """Response containing the current daemon status snapshot."""

    snapshot: DaemonStatusSnapshot
