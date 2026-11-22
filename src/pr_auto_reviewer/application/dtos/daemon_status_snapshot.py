from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.entities.api_access_capability import (
    ApiAccessCapability,
)
from pr_auto_reviewer.domain.value_objects.daemon_runtime_status import (
    DaemonRuntimeStatus,
)

@dataclass(frozen=True)
class DaemonStatusSnapshot:
    """Immutable application view of the daemon's current status."""

    runtime_status: DaemonRuntimeStatus | None
    daemon_alive: bool
    allowed_repositories: tuple[str, ...]
    capabilities: tuple[ApiAccessCapability, ...]
