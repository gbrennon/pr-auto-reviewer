from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, TYPE_CHECKING

import requests

from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import (
    RateLimitSnapshot,
)
from pr_auto_reviewer.infrastructure.client.rate_limit_tracker import (
    RateLimitTracker,
)

if TYPE_CHECKING:
    from pr_auto_reviewer.infrastructure.client.preflight_verifier import (
        PreflightVerifier,
    )
    from pr_auto_reviewer.infrastructure.client.token_resolver import TokenResolver
    from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId

logger = logging.getLogger(__name__)


class GitPlatformHttpClient:
    """HTTP client for GitHub and Forgejo/Codeberg REST APIs.

    Supports per-org token resolution via an optional ``TokenResolver`` and
    lazy preflight verification via an optional ``PreflightVerifier``.
    """
    def __init__(self, base_url: str, token: str, platform_mode: str = "forgejo", client_label: str = "", *, token_resolver: TokenResolver | None = None, preflight_verifier: PreflightVerifier | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._platform_mode = platform_mode
        self._role = client_label
        self._token_resolver = token_resolver
        self._preflight_verifier = preflight_verifier
        self._verified_orgs: set[tuple[str, str]] = set()
        self._rate_tracker = RateLimitTracker(token, platform_mode, client_label or "default")

    @property
    def base_url(self) -> str:
        return self._base_url

    def _label(self, action: str) -> str:
        return f" [{self._role}/{action}]" if self._role else ""

    def _resolve_token_for_repo(self, repo: str | None) -> str:
        """Return the token that should be used for requests scoped to
        *repo*, resolving a per-org override when one is configured."""
        if not repo or not self._token_resolver:
            return self._token
        return self._token_resolver.resolve(self._role, repo) or self._token

    def verify_token_for_pr(self, pr_id: PullRequestId) -> None:
        """Run preflight verification for the per-org token this client
        would use for *pr_id*.  No-op when no ``preflight_verifier`` is set,
        no per-org token is resolved, or the (org, role) pair has already
        been verified this session.

        Raises ``PreflightVerificationError`` on the first failure.
        """
        if not self._preflight_verifier or not self._token_resolver:
            return
        org = pr_id.repository.split("/", 1)[0]
        if not org:
            return
        role = "owner" if self._role == "owner" else "reviewer"
        cache_key = (org, role)
        if cache_key in self._verified_orgs:
            return
        token = self._resolve_token_for_repo(pr_id.repository)
        if token == self._token:
            return
        self._preflight_verifier.verify(
            token=token,
            org=org,
            repo=pr_id.repository.split("/", 1)[1] if "/" in pr_id.repository else pr_id.repository,
            pr_number=pr_id.number,
            role=role,
        )
        self._verified_orgs.add(cache_key)

    def _get_auth_header(self, repo: str | None = None) -> dict[str, str]:
        token = self._resolve_token_for_repo(repo)
        if self._platform_mode == "github":
            return {"Authorization": f"Bearer {token}"}
        return {"Authorization": f"token {token}"}

    def get(self, path: str, headers: dict[str, str] | None = None, *, repo: str | None = None, **params: Any) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        label = self._label("read")
        logger.info("GET%s %s params=%s", label, url, params)

        request_headers = self._get_auth_header(repo)
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

    def get_raw(self, path: str, headers: dict[str, str] | None = None, *, repo: str | None = None) -> str:
        url = f"{self._base_url}{path}"
        label = self._label("read")
        logger.info("GET_RAW%s %s", label, url)

        request_headers = self._get_auth_header(repo)
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

    def post(self, path: str, body: dict[str, Any], *, repo: str | None = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        label = self._label("write")
        logger.info("POST%s %s body_keys=%s", label, url, list(body.keys()))
        response = requests.post(
            url,
            headers={
                **self._get_auth_header(repo),
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
