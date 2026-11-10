"""DaemonRuntimeStatePort — outbound port for publishing and reading daemon telemetry."""

from __future__ import annotations

from typing import Protocol

from pr_auto_reviewer.domain.value_objects.daemon_runtime_status import (
    DaemonRuntimeStatus,
)


class DaemonRuntimeStatePort(Protocol):
    """Outbound port for persisting and reading real-time daemon state."""

    def record_status(self, status: DaemonRuntimeStatus) -> None:
        """Atomically persist daemon status snapshot."""
        ...

    def read_status(self) -> DaemonRuntimeStatus | None:
        """Read and parse the current daemon status snapshot if present."""
        ...

    def clear(self) -> None:
        """Clear daemon state upon clean termination."""
        ...
