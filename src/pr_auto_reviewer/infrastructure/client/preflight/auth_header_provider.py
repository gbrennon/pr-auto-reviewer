"""Provides platform-specific auth headers for preflight requests."""

from __future__ import annotations

from typing import Protocol


class AuthHeaderProvider(Protocol):
    def auth_header(self, token: str) -> dict[str, str]:
        """Return the ``Authorization`` header for *token*."""
        ...

    def write_access_extra_headers(self) -> dict[str, str]:
        """Return extra headers for write-access check (e.g. GitHub's Accept)."""
        ...
