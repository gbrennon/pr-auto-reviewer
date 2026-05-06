"""GitPlatformHttpClient — thin HTTP wrapper shared by git platform adapters.

Not a port. Never referenced outside the infrastructure layer.
Handles: base URL, Authorization header, response status assertion.
"""

from __future__ import annotations

from typing import Any

import requests


class GitPlatformHttpClient:
    """Thin HTTP client shared by all git platform adapters.

    Concrete implementations (e.g. ForgejoHttpClient) can extend or wrap
    this class with platform-specific quirks (pagination shape, auth scheme,
    rate limiting).
    """

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    @property
    def base_url(self) -> str:
        return self._base_url

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        response = requests.get(
            f"{self._base_url}{path}",
            headers={"Authorization": f"token {self._token}"},
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_raw(self, path: str) -> str:
        response = requests.get(
            f"{self._base_url}{path}",
            headers={"Authorization": f"token {self._token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.text

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self._base_url}{path}",
            headers={
                "Authorization": f"token {self._token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
