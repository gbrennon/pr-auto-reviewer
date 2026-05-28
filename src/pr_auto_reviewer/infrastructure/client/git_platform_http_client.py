"""GitPlatformHttpClient — thin HTTP wrapper shared by git platform adapters.

Not a port. Never referenced outside the infrastructure layer.
Handles: base URL, Authorization header, response status assertion.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


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
        url = f"{self._base_url}{path}"
        logger.info("GET %s params=%s", url, params)
        response = requests.get(
            url,
            headers={"Authorization": f"token {self._token}"},
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        response_body = getattr(response, "content", b"")
        logger.debug("GET %s -> %d (%d bytes)", url, response.status_code, len(response_body))
        result = response.json()
        logger.info("GET %s return: keys=%s", url, list(result.keys()) if isinstance(result, dict) else f"list[{len(result)}]")
        return result

    def get_raw(self, path: str) -> str:
        url = f"{self._base_url}{path}"
        logger.info("GET_RAW %s", url)
        response = requests.get(
            url,
            headers={"Authorization": f"token {self._token}"},
            timeout=30,
        )
        response.raise_for_status()
        response_body = getattr(response, "content", b"")
        logger.debug("GET_RAW %s -> %d (%d bytes)", url, response.status_code, len(response_body))
        result = response.text
        logger.info("GET_RAW %s return: %d chars", url, len(result))
        return result

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        logger.info("POST %s body_keys=%s", url, list(body.keys()))
        response = requests.post(
            url,
            headers={
                "Authorization": f"token {self._token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )
        response.raise_for_status()
        response_body = getattr(response, "content", b"")
        logger.debug("POST %s -> %d (%d bytes)", url, response.status_code, len(response_body))
        result = response.json()
        logger.info("POST %s return: keys=%s", url, list(result.keys()) if isinstance(result, dict) else f"list[{len(result)}]")
        return result
