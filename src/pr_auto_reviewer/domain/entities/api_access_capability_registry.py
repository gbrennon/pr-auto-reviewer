"""Aggregate root for API access capability availability."""

from __future__ import annotations

from dataclasses import dataclass, replace

from pr_auto_reviewer.domain.entities.api_access_capability import (
    ApiAccessCapability,
)
from pr_auto_reviewer.domain.value_objects.capability_suspension import (
    CapabilitySuspension,
)


@dataclass(frozen=True)
class ApiAccessCapabilityRegistry:
    """Own API capabilities and enforce temporary suspension decisions."""

    capabilities: tuple[ApiAccessCapability, ...] = ()

    @classmethod
    def empty(cls) -> ApiAccessCapabilityRegistry:
        """Create an empty capability registry."""
        return cls()

    def register(self, capability: ApiAccessCapability) -> ApiAccessCapabilityRegistry:
        """Return a registry containing *capability* without duplicate identity."""
        retained = tuple(
            item
            for item in self.capabilities
            if item.global_key != capability.global_key or item.scope != capability.scope
        )
        existing = next(
            (
                item
                for item in self.capabilities
                if item.global_key == capability.global_key and item.scope == capability.scope
            ),
            None,
        )
        registered = (
            capability
            if capability.suspension is not None or existing is None
            else replace(capability, suspension=existing.suspension)
        )
        return replace(self, capabilities=(*retained, registered))

    def suspend(
        self,
        capability: ApiAccessCapability,
        suspension: CapabilitySuspension,
    ) -> ApiAccessCapabilityRegistry:
        """Return a registry with every scope of *capability* suspended."""
        updated = tuple(
            replace(item, suspension=suspension)
            if item.global_key == capability.global_key
            else item
            for item in self.capabilities
        )
        if not any(item.global_key == capability.global_key for item in updated):
            updated = (*updated, replace(capability, suspension=suspension))
        return replace(self, capabilities=updated)

    def is_available(self, capability: ApiAccessCapability, now: float) -> bool:
        """Return whether the capability identity is available at *now*."""
        matching = [
            item for item in self.capabilities if item.global_key == capability.global_key
        ]
        return all(item.is_available(now) for item in matching)

    def statuses(self, now: float) -> tuple[ApiAccessCapability, ...]:
        """Return capabilities with expired suspensions removed from state."""
        return tuple(
            replace(item, suspension=None)
            if item.suspension is not None and not item.suspension.is_active(now)
            else item
            for item in self.capabilities
        )
