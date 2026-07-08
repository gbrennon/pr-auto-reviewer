from __future__ import annotations

import datetime as _dt
import logging
from typing import Any

import requests

from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import (
    RateLimitSnapshot,
)
from pr_auto_reviewer.infrastructure.client.rate_limit_tracker import (
    RateLimitTracker,
)

logger = logging.getLogger(__name__)


class GitPlatformHttpClient:
    def __init__(self, base_url: str, token: str, platform_mode: str = "forgejo", client_label: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._platform_mode = platform_mode
        self._role = client_label
        self._rate_tracker = RateLimitTracker(token, platform_mode, client_label or "default")

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

        response = requests.get(url, headers=request_headers, params=params, timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self._log_response_detail("GET", label, url, response)
            logger.error("GET%s %s failed with %s: %s", label, url, response.status_code, response.text)
            raise e

        self._log_response_detail("GET", label, url, response)
        return response.json()

    def get_raw(self, path: str, headers: dict[str, str] | None = None) -> str:
        url = f"{self._base_url}{path}"
        label = self._label("read")
        logger.info("GET_RAW%s %s", label, url)

        request_headers = self._get_auth_header()
        if headers:
            request_headers.update(headers)

        response = requests.get(url, headers=request_headers, timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self._log_response_detail("GET_RAW", label, url, response)
            logger.error("GET_RAW%s %s failed with %s: %s", label, url, response.status_code, response.text)
            raise e

        self._log_response_detail("GET_RAW", label, url, response)
        return response.text

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
            self._log_response_detail("POST", label, url, response)
            logger.error("POST%s %s failed with %s: %s", label, url, response.status_code, response.text)
            raise e

        self._log_response_detail("POST", label, url, response)
        return response.json()

    def _log_response_detail(self, method: str, label: str, url: str, response) -> None:
        status = response.status_code
        body_bytes = getattr(response, "content", b"")
        body_len = len(body_bytes)
        logger.info("%s%s %s -> HTTP %d (%d bytes)", method, label, url, status, body_len)

        if logger.isEnabledFor(logging.INFO):
            text = response.text
            if text:
                truncated = text[:2000]
                logger.info(
                    "%s%s %s body (%d chars):\n%s",
                    method, label, url, len(text),
                    truncated + ("..." if len(text) > 2000 else ""),
                )

        self._capture_rate_limit(getattr(response, "headers", {}))
        self._write_http_log(method, label, url, response)

    def _capture_rate_limit(self, headers: dict[str, str]) -> None:
        if "x-ratelimit-limit" not in headers:
            return
        snapshot = RateLimitSnapshot.from_response_headers(headers)
        self._rate_tracker.record(snapshot)

    def _write_http_log(self, method: str, label: str, url: str, response) -> None:
        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        clean_label = label.replace("[", "").replace("]", "").replace("/", "_")
        filename = f"/tmp/http-{timestamp}-{clean_label}-{response.status_code}.log"
        try:
            with open(filename, "w") as f:
                f.write(f"{method}{label} {url}\n")
                f.write(f"Status: {response.status_code}\n")
                for k, v in getattr(response, "headers", {}).items():
                    if k.lower() != "authorization":
                        f.write(f"{k}: {v}\n")
                f.write("\n")
                f.write(response.text)
            logger.info("%s%s response dumped to %s", method, label, filename)
        except (OSError, AttributeError):
            pass
