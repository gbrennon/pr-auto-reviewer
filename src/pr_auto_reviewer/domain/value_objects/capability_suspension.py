"""Temporary suspension details for an API access capability."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilitySuspension:
    """Describe why an API capability is unavailable until a reset time."""

    suspended_until: float
    resource: str
    remaining: int
    limit: int
    reason: str

    def is_active(self, now: float) -> bool:
        """Return whether the suspension still applies at *now*."""
        return now < self.suspended_until

    def remaining_seconds(self, now: float) -> int:
        """Return whole seconds remaining in the suspension."""
        return max(0, int(self.suspended_until - now))
