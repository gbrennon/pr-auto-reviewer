"""Global credential presentation port."""

from __future__ import annotations

from typing import Protocol


class GlobalCredentialPort(Protocol):
    """Manage platform-global role credentials."""

    def save_global_credential(self, platform: str, role: str, token: str) -> None:
        """Set or clear one platform-global role credential."""
        ...
