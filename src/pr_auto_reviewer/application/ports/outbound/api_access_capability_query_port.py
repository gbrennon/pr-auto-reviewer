"""Outbound port for querying API access capability status."""

from typing import Protocol

from ....domain.entities.api_access_capability import ApiAccessCapability


class ApiAccessCapabilityQueryPort(Protocol):
    """Provide current API capability status projections."""

    def statuses(self) -> tuple[ApiAccessCapability, ...]:
        """Return every known capability with its current availability."""
        ...
