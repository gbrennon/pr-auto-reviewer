from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class GitPlatformHttpClient:
    def __init__(self, base_url: str, token: str, platform_mode: str = "codeberg", client_label: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._platform_mode = platform_mode
        self._role = client_label

    @property
    def base_url(self) -> str:
        return self._base_url

    def _label(self, action: str) -> str:
        return f" [{self._role}/{action}]" if self._role else ""

    def _get_auth_header(self) -> dict[str, str]:
        if self._platform_mode == "github":
            return {"Authorization": f"Bearer {self._token}"}
        return {"Authorization": f"token {self._token}"}

    def get(self, path: str, headers: dict[str, str] | None = None, **params: Any) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        label = self._label("read")
        logger.info("GET%s %s params=%s", label, url, params)

        request_headers = self._get_auth_header()
        if headers:
            request_headers.update(headers)

        response = requests.get(
            url,
            headers=request_headers,
            params=params,
            timeout=30,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(
                "GET%s %s failed with %s: %s",
                label, url, response.status_code, response.text,
            )
            raise e
        response_body = getattr(response, "content", b"")
        logger.debug("GET%s %s -> %d (%d bytes)", label, url, response.status_code, len(response_body))
        result = response.json()
        logger.info("GET%s %s return: keys=%s", label, url, list(result.keys()) if isinstance(result, dict) else f"list[{len(result)}]")
        return result

    def get_raw(self, path: str, headers: dict[str, str] | None = None) -> str:
        url = f"{self._base_url}{path}"
        label = self._label("read")
        logger.info("GET_RAW%s %s", label, url)

        request_headers = self._get_auth_header()
        if headers:
            request_headers.update(headers)

        response = requests.get(
            url,
            headers=request_headers,
            timeout=30,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(
                "GET_RAW%s %s failed with %s: %s",
                label, url, response.status_code, response.text,
            )
            raise e
        response_body = getattr(response, "content", b"")
        logger.debug("GET_RAW%s %s -> %d (%d bytes)", label, url, response.status_code, len(response_body))
        result = response.text
        logger.info("GET_RAW%s %s return: %d chars", label, url, len(result))
        return result

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        label = self._label("write")
        logger.info("POST%s %s body_keys=%s", label, url, list(body.keys()))
        response = requests.post(
            url,
            headers={
                **self._get_auth_header(),
                "Content-Type": "application/json",
                "User-Agent": "pr-auto-reviewer",
            },
            json=body,
            timeout=30,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(
                "POST%s %s failed with %s: %s",
                label, url, response.status_code, response.text,
            )
            raise e
        response_body = getattr(response, "content", b"")
        logger.debug("POST%s %s -> %d (%d bytes)", label, url, response.status_code, len(response_body))
        result = response.json()
        logger.info("POST%s %s return: keys=%s", label, url, list(result.keys()) if isinstance(result, dict) else f"list[{len(result)}]")
        return result
