"""API access capability entity."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.value_objects.capability_suspension import (
    CapabilitySuspension,
)


@dataclass(frozen=True)
class ApiAccessCapability:
    """A named platform capability scoped to a repository or organization."""

    platform: str
    role: str
    source_name: str
    scope: str
    suspension: CapabilitySuspension | None = None

    @property
    def global_key(self) -> tuple[str, str, str]:
        """Return the key shared by all scopes using this API capability."""
        return self.platform, self.role, self.source_name

    def is_available(self, now: float) -> bool:
        """Return whether this capability can be used at *now*."""
        return self.suspension is None or not self.suspension.is_active(now)
