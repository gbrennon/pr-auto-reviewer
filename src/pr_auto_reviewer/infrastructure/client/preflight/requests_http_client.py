"""Real HTTP client for preflight checks using ``requests``."""

from __future__ import annotations

from typing import Any

import requests


class RequestsHttpClient:
    def __init__(self, base_url: str, *, timeout: int = 10) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get(self, path: str, *, headers: dict[str, str]) -> requests.Response:
        return requests.get(
            f"{self._base_url}{path}",
            headers=headers,
            timeout=self._timeout,
        )

    def post(
        self, path: str, *, headers: dict[str, str], json: dict[str, Any]
    ) -> requests.Response:
        return requests.post(
            f"{self._base_url}{path}",
            headers=headers,
            json=json,
            timeout=self._timeout,
        )
