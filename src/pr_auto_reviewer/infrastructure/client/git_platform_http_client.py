from __future__ import annotations

import datetime as _dt
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from pr_auto_reviewer.domain.entities.api_access_capability import (
    ApiAccessCapability,
)
from pr_auto_reviewer.domain.value_objects.capability_suspension import (
    CapabilitySuspension,
)
from pr_auto_reviewer.infrastructure.client.api_access_capability_state import (
    ApiAccessCapabilityState,
)
from pr_auto_reviewer.infrastructure.client.api_access_capability_store import (
    ApiAccessCapabilityStore,
)
from pr_auto_reviewer.infrastructure.client.http_request_counter import (
    HttpRequestCounter,
)
from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import (
    RateLimitSnapshot,
)
from pr_auto_reviewer.infrastructure.config.app_paths import AppPaths

if TYPE_CHECKING:
    from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
    from pr_auto_reviewer.infrastructure.client.preflight_verifier import (
        PreflightVerifier,
    )
    from pr_auto_reviewer.infrastructure.client.token_resolver import TokenResolver
logger = logging.getLogger(__name__)


class GitPlatformHttpClient:
    """HTTP client for GitHub and Forgejo/Codeberg REST APIs.

    """

    def __init__(
        self,
        base_url: str,
        token: str,
        platform_mode: str = "forgejo",
        client_label: str = "",
        *,
        token_resolver: TokenResolver | None = None,
        preflight_verifier: PreflightVerifier | None = None,
        _verified_cache_path: Path | None = None,
        capability_state: ApiAccessCapabilityState | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._platform_mode = platform_mode
        self._role = client_label
        self._token_resolver = token_resolver
        self._preflight_verifier = preflight_verifier
        self._verified_cache_path = (
            _verified_cache_path or AppPaths.cache_dir() / "verified-tokens.json"
        )
        self._capability_state = capability_state or ApiAccessCapabilityState(
            ApiAccessCapabilityStore(AppPaths.state_dir() / "api-capabilities.json")
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    def get(self, path: str, headers: dict[str, str] | None = None, *, repo: str | None = None, **params: Any) -> dict[str, Any]:
        token, capability = self._request_credentials(repo)
        url = f"{self._base_url}{path}"
        label = self._label("read")
        request_headers = self._auth_header(token)
        if headers:
            request_headers.update(headers)

        response = requests.get(url, headers=request_headers, params=params, timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            self._log_response_detail("GET", label, url, response, repo=repo, capability=capability)
            logger.error("GET%s %s failed with %s: %s", label, url, response.status_code, response.text)
            raise

        self._log_response_detail("GET", label, url, response, repo=repo, capability=capability)
        return response.json()

    def get_raw(self, path: str, headers: dict[str, str] | None = None, *, repo: str | None = None) -> str:
        token, capability = self._request_credentials(repo)
        url = f"{self._base_url}{path}"
        label = self._label("read")
        request_headers = self._auth_header(token)
        if headers:
            request_headers.update(headers)

        response = requests.get(url, headers=request_headers, timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            self._log_response_detail("GET_RAW", label, url, response, repo=repo, capability=capability)
            logger.error("GET_RAW%s %s failed with %s: %s", label, url, response.status_code, response.text)
            raise

        self._log_response_detail("GET_RAW", label, url, response, repo=repo, capability=capability)
        return response.text

    def post(self, path: str, body: dict[str, Any], *, repo: str | None = None) -> dict[str, Any]:
        token, capability = self._request_credentials(repo)
        url = f"{self._base_url}{path}"
        label = self._label("write")
        response = requests.post(
            url,
            headers={
                **self._auth_header(token),
                "Content-Type": "application/json",
                "User-Agent": "pr-auto-reviewer",
            },
            json=body,
            timeout=30,
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            self._log_response_detail("POST", label, url, response, repo=repo, capability=capability)
            logger.error("POST%s %s failed with %s: %s", label, url, response.status_code, response.text)
            raise

        self._log_response_detail("POST", label, url, response, repo=repo, capability=capability)
        return response.json()

    def is_capability_available(self, repo: str) -> bool:
        """Return whether the resolved API capability can serve *repo*."""
        source_name = self._resolve_token_source_for_repo(repo)[1]
        return self._capability_state.is_available(
            self._platform_mode,
            self._role or "default",
            source_name,
            repo,
        )

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
        # Strip internal platform prefix (forgejo:, github:) from org for API calls
        if ":" in org:
            org = org.split(":", 1)[1]
        role = "owner" if self._role == "owner" else "reviewer"
        cache_key = (org, role)
        if cache_key in self._load_verified_cache():
            return
        token, source_key = self._token_resolver.resolve_source(
            self._role, pr_id.repository
        )
        if not token:
            return
        self._save_verified_cache(cache_key)
        self._preflight_verifier.verify(
            token=token,
            org=org,
            repo=pr_id.repository.split("/", 1)[1] if "/" in pr_id.repository else pr_id.repository,
            pr_number=pr_id.number,
            role=role,
            token_source=source_key,
        )

    def _capture_rate_limit(
        self,
        headers: dict[str, str],
        capability: ApiAccessCapability,
    ) -> None:
        if "x-ratelimit-limit" not in headers:
            return
        snapshot = RateLimitSnapshot.from_response_headers(headers)
        if not snapshot.exhausted():
            return
        wait_seconds = max(60, snapshot.reset_seconds_from_now())
        self._capability_state.suspend(
            capability,
            CapabilitySuspension(
                suspended_until=time.time() + wait_seconds,
                resource=snapshot.resource,
                remaining=snapshot.remaining,
                limit=snapshot.limit,
                reason="rate_limit_exhausted",
            ),
        )

    def _get_auth_header(self, repo: str | None = None) -> dict[str, str]:
        token = self._resolve_token_for_repo(repo)
        return self._auth_header(token)

    def _request_credentials(
        self, repo: str | None,
    ) -> tuple[str, ApiAccessCapability]:
        token, source_name = self._resolve_token_source_for_repo(repo)
        capability = self._capability_state.require_available(
            self._platform_mode,
            self._role or "default",
            source_name,
            repo or "",
        )
        return token, capability

    def _auth_header(self, token: str) -> dict[str, str]:
        if self._platform_mode == "github":
            return {"Authorization": f"Bearer {token}"}
        return {"Authorization": f"token {token}"}

    def _label(self, action: str) -> str:
        return f" [{self._role}/{action}]" if self._role else ""

    def _load_verified_cache(self) -> set[tuple[str, str]]:
        """Load verified (org, role) pairs from the persisted cache file.

        Returns an empty set when the file is missing or malformed -- the
        cache is best-effort and must never prevent the client from working.
        """
        if not self._verified_cache_path.exists():
            return set()
        try:
            data = json.loads(self._verified_cache_path.read_text())
            return {tuple(pair) for pair in data}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load verified token cache: %s", exc)
            return set()

    def _log_response_detail(
        self,
        method: str,
        label: str,
        url: str,
        response: Any,
        repo: str | None = None,
        capability: ApiAccessCapability | None = None,
    ) -> None:
        if capability is not None:
            self._capture_rate_limit(getattr(response, "headers", {}), capability)
        self._write_http_log(method, label, url, response)
        HttpRequestCounter.instance().record(self._base_url)

    def _resolve_token_for_repo(self, repo: str | None) -> str:
        """Return the token that should be used for requests scoped to *repo*."""
        token, _ = self._resolve_token_source_for_repo(repo)
        return token

    def _resolve_token_source_for_repo(
        self, repo: str | None,
    ) -> tuple[str, str]:
        if repo and self._token_resolver:
            token, source_name = self._token_resolver.resolve_source(
                self._role, repo
            )
            if token:
                return token, source_name
        role = self._role.upper() if self._role else "DEFAULT"
        return self._token, f"{self._platform_mode.upper()}_{role}_TOKEN"

    def _save_verified_cache(self, cache_key: tuple[str, str]) -> None:
        """Persist the current ``_verified_orgs`` set to disk, merged with
        existing file contents so that writes from different client instances
        (owner/reviewer) accumulate rather than overwrite each other.

        Best-effort -- write failures are logged but never raised so that
        a transient disk issue does not block the review pipeline.
        """

        try:
            existing = self._load_verified_cache()
            merged = existing | {cache_key}
            self._verified_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._verified_cache_path.write_text(
                json.dumps(sorted(merged))
            )
        except OSError as exc:
            logger.warning("Failed to save verified token cache: %s", exc)

    def _write_http_log(self, method: str, label: str, url: str, response) -> None:
        timestamp = _dt.datetime.now(_dt.UTC).strftime("%Y%m%d_%H%M%S_%f")
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
            logger.debug("%s%s response dumped to %s", method, label, filename)
        except (OSError, AttributeError):
            pass
