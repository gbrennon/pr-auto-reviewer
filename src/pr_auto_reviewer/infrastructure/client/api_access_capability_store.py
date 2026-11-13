"""JSON persistence for API access capability suspension state."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from pr_auto_reviewer.domain.entities.api_access_capability import (
    ApiAccessCapability,
)
from pr_auto_reviewer.domain.entities.api_access_capability_registry import (
    ApiAccessCapabilityRegistry,
)
from pr_auto_reviewer.domain.value_objects.capability_suspension import (
    CapabilitySuspension,
)

logger = logging.getLogger(__name__)


class ApiAccessCapabilityStore:
    """Persist capability suspension state without token values."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self, now: float | None = None) -> ApiAccessCapabilityRegistry:
        """Load persisted capabilities and clear expired suspensions."""
        if not self._path.exists():
            return ApiAccessCapabilityRegistry.empty()
        try:
            data = json.loads(self._path.read_text())
            capabilities = data.get("capabilities", [])
            current_time = time.time() if now is None else now
            parsed = tuple(
                self._parse_capability(item, current_time)
                for item in capabilities
                if isinstance(item, dict)
            )
            return ApiAccessCapabilityRegistry(capabilities=parsed)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load API capability state from %s: %s", self._path, exc)
            return ApiAccessCapabilityRegistry.empty()

    def save(self, registry: ApiAccessCapabilityRegistry) -> None:
        """Persist active capability state and omit expired suspensions."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "capabilities": [
                    self._serialize_capability(capability)
                    for capability in registry.statuses(time.time())
                ]
            }
            self._path.write_text(json.dumps(data, indent=2, sort_keys=True))
        except OSError as exc:
            logger.warning("Failed to save API capability state to %s: %s", self._path, exc)

    def _parse_capability(
        self, data: dict[str, object], now: float,
    ) -> ApiAccessCapability:
        suspension_data = data.get("suspension")
        suspension = None
        if isinstance(suspension_data, dict):
            parsed = CapabilitySuspension(
                suspended_until=float(suspension_data["suspended_until"]),
                resource=str(suspension_data.get("resource", "")),
                remaining=int(suspension_data.get("remaining", 0)),
                limit=int(suspension_data.get("limit", 0)),
                reason=str(suspension_data.get("reason", "")),
            )
            if parsed.is_active(now):
                suspension = parsed
        return ApiAccessCapability(
            platform=str(data["platform"]),
            role=str(data["role"]),
            source_name=str(data["source_name"]),
            scope=str(data.get("scope", "")),
            suspension=suspension,
        )

    def _serialize_capability(
        self, capability: ApiAccessCapability,
    ) -> dict[str, object]:
        suspension = capability.suspension
        return {
            "platform": capability.platform,
            "role": capability.role,
            "source_name": capability.source_name,
            "scope": capability.scope,
            "suspension": (
                {
                    "suspended_until": suspension.suspended_until,
                    "resource": suspension.resource,
                    "remaining": suspension.remaining,
                    "limit": suspension.limit,
                    "reason": suspension.reason,
                }
                if suspension is not None
                else None
            ),
        }
