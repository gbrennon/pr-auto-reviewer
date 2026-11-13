"""Outbound port for API access capability suspension persistence."""

from __future__ import annotations

from typing import Protocol

from pr_auto_reviewer.domain.entities.api_access_capability_registry import (
    ApiAccessCapabilityRegistry,
)


class ApiAccessCapabilityStorePort(Protocol):
    """Persist the API access capability registry."""

    def load(self, now: float | None = None) -> ApiAccessCapabilityRegistry:
        """Load capability state, treating expired suspensions as available."""
        ...

    def save(self, registry: ApiAccessCapabilityRegistry) -> None:
        """Persist capability state without secret token values."""
        ...
