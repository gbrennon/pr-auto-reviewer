"""HTTP client Protocol for preflight checks."""

from __future__ import annotations

from typing import Any, Protocol


class PreflightHttpClient(Protocol):
    def get(self, path: str, *, headers: dict[str, str]) -> Any:
        ...

    def post(
        self, path: str, *, headers: dict[str, str], json: dict[str, Any]
    ) -> Any:
        ...