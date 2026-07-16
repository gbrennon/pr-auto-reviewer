"""PreflightVerifier — validates token auth and write access before review."""

from __future__ import annotations

import logging

import requests

from pr_auto_reviewer.domain.exceptions.preflight_verification_error import (
    PreflightVerificationError,
)
from pr_auto_reviewer.infrastructure.client.preflight.auth_header_provider import (
    AuthHeaderProvider,
)
from pr_auto_reviewer.infrastructure.client.preflight.preflight_http_client import (
    PreflightHttpClient,
)

logger = logging.getLogger(__name__)


class PreflightVerifier:
    """Verify that a platform token has valid auth + write access.

    Args:
        http_client: ``PreflightHttpClient`` for the target platform.
        auth_headers: Platform-specific auth header provider.
        base_url: API base URL for error messages.
        platform: Platform name for error messages (``"github"`` or ``"forgejo"``).
    """

    def __init__(
        self,
        http_client: PreflightHttpClient,
        auth_headers: AuthHeaderProvider,
        base_url: str,
        platform: str,
    ) -> None:
        self._http = http_client
        self._auth = auth_headers
        self._base_url = base_url.rstrip("/")
        self._platform = platform.lower()

    def verify(
        self,
        token: str,
        org: str,
        repo: str,
        pr_number: int,
        role: str = "owner",
        token_source: str = "",
    ) -> None:
        logger.debug(
            "Preflight for %s/%s (%s token): verifying auth…",
            org, repo, role,
        )
        self._check_auth(token, org, role, token_source)

        logger.debug(
            "Preflight for %s/%s (%s token): verifying write access…",
            org, repo, role,
        )
        self._check_write_access(token, org, repo, pr_number, role, token_source)

        logger.info(
            "Preflight passed for %s/%s (%s token).",
            org, repo, role,
        )

    def _check_auth(
        self, token: str, org: str, role: str, token_source: str = ""
    ) -> None:
        headers = self._auth.auth_header(token)
        try:
            resp = self._http.get("/user", headers=headers)
        except requests.RequestException as exc:
            raise PreflightVerificationError(
                platform=self._platform, org=org, role=role,
                http_status=0, step="auth", token_source=token_source,
                url=f"{self._base_url}/user", method="GET",
            ) from exc
        if resp.status_code != 200:
            raise PreflightVerificationError(
                platform=self._platform, org=org, role=role,
                http_status=resp.status_code, step="auth",
                token_source=token_source,
                url=f"{self._base_url}/user", method="GET",
            )

    def _check_write_access(
        self, token: str, org: str, repo: str,
        pr_number: int, role: str, token_source: str = "",
    ) -> None:
        headers = {
            **self._auth.auth_header(token),
            "Content-Type": "application/json",
            **self._auth.write_access_extra_headers(),
        }
        path = f"/repos/{org}/{repo}/pulls/{pr_number}/requested_reviewers"
        url = f"{self._base_url}{path}"

        try:
            resp = self._http.post(path, headers=headers, json={"reviewers": []})
        except requests.RequestException as exc:
            raise PreflightVerificationError(
                platform=self._platform, org=org, role=role,
                http_status=0, step="write_access", token_source=token_source,
                url=url, method="POST",
            ) from exc

        if resp.status_code in (401, 403):
            raise PreflightVerificationError(
                platform=self._platform, org=org, role=role,
                http_status=resp.status_code, step="write_access",
                token_source=token_source, url=url, method="POST",
            )