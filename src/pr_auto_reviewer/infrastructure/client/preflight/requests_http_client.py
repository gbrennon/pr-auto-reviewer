"""Real HTTP client for preflight checks using ``requests``."""

from __future__ import annotations

from typing import Any

import requests

from pr_auto_reviewer.infrastructure.client.remote_host_backoff import (
    RemoteHostBackoff,
)



class RequestsHttpClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: int = 10,
        remote_host_backoff: RemoteHostBackoff | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._remote_host_backoff = (
            remote_host_backoff
            if remote_host_backoff is not None
            else RemoteHostBackoff()
        )
        self._remote_host = RemoteHostBackoff.host_from_url(self._base_url)

    def get(self, path: str, *, headers: dict[str, str]) -> requests.Response:
        self._remote_host_backoff.before_operation(self._remote_host)
        try:
            response = requests.get(
                f"{self._base_url}{path}",
                headers=headers,
                timeout=self._timeout,
            )
        except requests.exceptions.RequestException as exc:
            self._record_request_exception(exc)
            raise
        self._record_response(response)
        return response

    def post(
        self, path: str, *, headers: dict[str, str], json: dict[str, Any]
    ) -> requests.Response:
        self._remote_host_backoff.before_operation(self._remote_host)
        try:
            response = requests.post(
                f"{self._base_url}{path}",
                headers=headers,
                json=json,
                timeout=self._timeout,
            )
        except requests.exceptions.RequestException as exc:
            self._record_request_exception(exc)
            raise
        self._record_response(response)
        return response

    def _record_response(self, response: requests.Response) -> None:
        status_code = response.status_code
        if status_code == 429 or status_code >= 500:
            self._remote_host_backoff.record_failure(self._remote_host)
        else:
            self._remote_host_backoff.record_success(self._remote_host)

    def _record_request_exception(
        self, exc: requests.exceptions.RequestException,
    ) -> None:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code is None or status_code == 429 or status_code >= 500:
            self._remote_host_backoff.record_failure(self._remote_host)
        else:
            self._remote_host_backoff.record_success(self._remote_host)
