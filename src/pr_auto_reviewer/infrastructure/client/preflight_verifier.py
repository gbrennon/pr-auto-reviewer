"""PreflightVerifier — validates a per-org token before first use.

On first resolution of a per-org token for an (org, role) pair the verifier
runs two side-effect-free API calls:

1.  ``GET /user`` — confirms the token is valid (not expired/revoked).
2.  ``POST …/requested_reviewers {\"reviewers\": []}`` — confirms the
    token has write permission on the target repo (empty reviewers list
    leaves no side effect).

Both GitHub and Forgejo/Codeberg are supported.  HTTP status codes
200 / 422 mean *pass*; 401 / 403 mean *fail*.
"""

from __future__ import annotations

import logging
from typing import ClassVar

import requests

from pr_auto_reviewer.domain.exceptions.preflight_verification_error import (
    PreflightVerificationError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class PreflightVerifier:
    """Verify that a platform token has valid auth + write access.

    The verifier makes two HTTP calls directly (not through
    ``GitPlatformHttpClient``) so there is no circular dependency.
    """

    _TIMEOUT: ClassVar[int] = 10  # seconds per HTTP call

    def __init__(self, base_url: str, platform_mode: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._platform = platform_mode.lower()  # "github" | "forgejo"

    # ------------------------------------------------------------------
    def verify(
        self,
        token: str,
        org: str,
        repo: str,
        pr_number: int,
        role: str = "owner",
    ) -> None:
        """Run both preflight checks.  Raises ``PreflightVerificationError``
        on the first failure."""

        logger.debug(
            "Preflight for %s/%s (%s token): verifying auth…",
            org, repo, role,
        )
        self._check_auth(token, org, role)

        logger.debug(
            "Preflight for %s/%s (%s token): verifying write access…",
            org, repo, role,
        )
        self._check_write_access(token, org, repo, pr_number, role)

        logger.info(
            "Preflight passed for %s/%s (%s token).",
            org, repo, role,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_auth(self, token: str, org: str, role: str) -> None:
        headers = self._auth_header(token)
        url = f"{self._base_url}/user"
        try:
            resp = requests.get(url, headers=headers, timeout=self._TIMEOUT)
        except requests.RequestException as exc:
            raise PreflightVerificationError(
                platform=self._platform, org=org, role=role,
                http_status=0, step="auth",
            ) from exc
        if resp.status_code != 200:
            raise PreflightVerificationError(
                platform=self._platform, org=org, role=role,
                http_status=resp.status_code, step="auth",
            )

    def _check_write_access(
        self, token: str, org: str, repo: str, pr_number: int, role: str,
    ) -> None:
        headers = self._auth_header(token)
        headers["Content-Type"] = "application/json"
        if self._platform == "github":
            headers["Accept"] = "application/vnd.github.v3+json"

        path = f"/repos/{org}/{repo}/pulls/{pr_number}/requested_reviewers"
        url = f"{self._base_url}{path}"

        try:
            resp = requests.post(
                url, headers=headers, json={"reviewers": []},
                timeout=self._TIMEOUT,
            )
        except requests.RequestException as exc:
            raise PreflightVerificationError(
                platform=self._platform, org=org, role=role,
                http_status=0, step="write_access",
            ) from exc

        if resp.status_code in (401, 403):
            raise PreflightVerificationError(
                platform=self._platform, org=org, role=role,
                http_status=resp.status_code, step="write_access",
            )
        # 200 and 422 both mean pass (422 = PR not found / repo exists but
        # PR number wrong — still proves write access on the *repo*).

    def _auth_header(self, token: str) -> dict[str, str]:
        if self._platform == "github":
            return {"Authorization": f"Bearer {token}"}
        return {"Authorization": f"token {token}"}
