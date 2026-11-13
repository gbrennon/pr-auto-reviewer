"""Infrastructure coordinator for the immutable capability aggregate."""

from __future__ import annotations

import time
from dataclasses import dataclass

from pr_auto_reviewer.application.ports.outbound.api_access_capability_store_port import (
    ApiAccessCapabilityStorePort,
)
from pr_auto_reviewer.domain.entities.api_access_capability import (
    ApiAccessCapability,
)
from pr_auto_reviewer.domain.entities.api_access_capability_registry import (
    ApiAccessCapabilityRegistry,
)
from pr_auto_reviewer.domain.exceptions.api_access_capability_suspended_error import (
    ApiAccessCapabilitySuspendedError,
)
from pr_auto_reviewer.domain.value_objects.capability_suspension import (
    CapabilitySuspension,
)


@dataclass(frozen=True)
class ApiAccessCapabilityState:
    """Coordinate aggregate persistence at infrastructure edges."""

    store: ApiAccessCapabilityStorePort

    @property
    def registry(self) -> ApiAccessCapabilityRegistry:
        """Return the current capability aggregate."""
        return self.store.load()

    def is_available(
        self,
        platform: str,
        role: str,
        source_name: str,
        scope: str,
    ) -> bool:
        """Return whether a source capability is available for a scope."""
        capability = self._capability(platform, role, source_name, scope)
        return self.registry.is_available(capability, time.time())

    def require_available(
        self,
        platform: str,
        role: str,
        source_name: str,
        scope: str,
    ) -> ApiAccessCapability:
        """Return a capability or raise when its API key is suspended."""
        capability = self._capability(platform, role, source_name, scope)
        registry = self.registry.register(capability)
        self.store.save(registry)
        now = time.time()
        if registry.is_available(capability, now):
            return capability
        suspension = next(
            item.suspension
            for item in registry.capabilities
            if item.global_key == capability.global_key and item.suspension is not None
        )
        raise ApiAccessCapabilitySuspendedError(
            capability.source_name,
            suspension.remaining_seconds(now),
        )

    def suspend(
        self,
        capability: ApiAccessCapability,
        suspension: CapabilitySuspension,
    ) -> None:
        """Suspend and persist a capability through the aggregate root."""
        registry = self.registry.register(capability).suspend(capability, suspension)
        self.store.save(registry)

    def statuses(self) -> tuple[ApiAccessCapability, ...]:
        """Return current capability status projections."""
        return self.registry.statuses(time.time())

    def _capability(
        self,
        platform: str,
        role: str,
        source_name: str,
        scope: str,
    ) -> ApiAccessCapability:
        return ApiAccessCapability(
            platform=platform,
            role=role,
            source_name=source_name,
            scope=scope,
        )
