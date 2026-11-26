from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import requests

from pr_auto_reviewer.domain.entities.api_access_capability import (
    ApiAccessCapability,
)
from pr_auto_reviewer.domain.exceptions.preflight_verification_error import (
    PreflightVerificationError,
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
from pr_auto_reviewer.infrastructure.client.remote_host_backoff import (
    RemoteHostBackoff,
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
        remote_host_backoff: RemoteHostBackoff | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._remote_host_backoff = (
            remote_host_backoff
            if remote_host_backoff is not None
            else RemoteHostBackoff()
        )
        self._remote_host = RemoteHostBackoff.host_from_url(self._base_url)
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

        keys = self._operation_keys(url, capability)
        self._remote_host_backoff.before_operation(*keys)
        try:
            response = requests.get(
                url, headers=request_headers, params=params, timeout=30,
            )
        except requests.exceptions.RequestException as exc:
            self._record_request_exception(exc, keys)
            raise
        self._record_remote_response(response, keys)
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

        keys = self._operation_keys(url, capability)
        self._remote_host_backoff.before_operation(*keys)
        try:
            response = requests.get(url, headers=request_headers, timeout=30)
        except requests.exceptions.RequestException as exc:
            self._record_request_exception(exc, keys)
            raise
        self._record_remote_response(response, keys)
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
        keys = self._operation_keys(url, capability)
        self._remote_host_backoff.before_operation(*keys)
        try:
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
        except requests.exceptions.RequestException as exc:
            self._record_request_exception(exc, keys)
            raise
        self._record_remote_response(response, keys)
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
        no per-org token is resolved, or the token identity is already
        verified in the persisted cache.

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
        role = "manager" if self._role == "manager" else "reviewer"
        token, source_key = self._token_resolver.resolve_source(
            self._role, pr_id.repository
        )
        if not token:
            return
        fingerprint = hashlib.sha256(token.encode()).hexdigest()
        cache_key = (org, role, source_key, fingerprint)
        if cache_key in self._load_verified_cache():
            return
        capability_key = (
            f"capability:{self._platform_mode}:"
            f"{self._role or 'default'}:{source_key}"
        )
        self._remote_host_backoff.before_operation(
            self._remote_host, capability_key,
        )
        try:
            self._preflight_verifier.verify(
                token=token,
                org=org,
                repo=pr_id.repository.split("/", 1)[1] if "/" in pr_id.repository else pr_id.repository,
                pr_number=pr_id.number,
                role=role,
                token_source=source_key,
            )
        except PreflightVerificationError:
            self._remote_host_backoff.record_failure(capability_key)
            raise
        self._remote_host_backoff.record_success(capability_key)
        self._save_verified_cache(cache_key)

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

    def _operation_keys(
        self, url: str, capability: ApiAccessCapability,
    ) -> tuple[str | None, str, str]:
        capability_key = "capability:" + ":".join(capability.global_key)
        return self._remote_host, capability_key, f"operation:{url}"

    @staticmethod
    def _cache_key_from_entry(
        entry: dict[str, Any],
    ) -> tuple[str, str, str, str] | None:
        org = entry.get("org")
        role = entry.get("role")
        source = entry.get("source")
        fingerprint = entry.get("fingerprint")
        if not all(
            isinstance(value, str)
            for value in (org, role, source, fingerprint)
        ):
            return None
        return cast(
            tuple[str, str, str, str],
            (org, role, source, fingerprint),
        )

    def _load_verified_cache(self) -> set[tuple[str, str, str, str]]:
        """Load verified token identities from the persisted cache file.

        Returns an empty set when the file is missing, malformed, or contains
        legacy pair-only entries.
        """
        if not self._verified_cache_path.exists():
            return set()
        try:
            data = json.loads(self._verified_cache_path.read_text())
            if not isinstance(data, list):
                return set()
            return {
                cache_key
                for entry in data
                if isinstance(entry, dict)
                and (
                    cache_key := self._cache_key_from_entry(entry)
                ) is not None
            }
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load verified token cache: %s", exc)
            return set()

    def _record_remote_response(
        self,
        response: Any,
        keys: tuple[str | None, str, str],
    ) -> None:
        host_key, _, _ = keys
        status_code = getattr(response, "status_code", 0)
        if status_code == 429 or status_code >= 500:
            self._remote_host_backoff.record_failure(host_key)
            return
        if 400 <= status_code < 500:
            self._remote_host_backoff.record_success(host_key)
            return
        self._remote_host_backoff.record_success(host_key)

    def _record_request_exception(
        self,
        exc: requests.exceptions.RequestException,
        keys: tuple[str | None, str, str],
    ) -> None:
        host_key, _, _ = keys
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code is not None and 400 <= status_code < 500:
            self._remote_host_backoff.record_success(host_key)
            return
        self._remote_host_backoff.record_failure(host_key)

    def _run_remote_command(
        self,
        runner: Any,
        command: list[str],
        input_text: str | None = None,
    ) -> str:
        """Run a CLI command while applying host backoff bookkeeping."""
        self._remote_host_backoff.before_operation(self._remote_host)
        try:
            output = runner.run(command, input_text)
        except Exception:
            self._remote_host_backoff.record_failure(self._remote_host)
            raise
        self._remote_host_backoff.record_success(self._remote_host)
        return output

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

    def _save_verified_cache(
        self, cache_key: tuple[str, str, str, str],
    ) -> None:
        """Persist verified token identities to disk."""
        try:
            existing = self._load_verified_cache()
            merged = existing | {cache_key}
            records = [
                {
                    "fingerprint": fingerprint,
                    "org": org,
                    "role": role,
                    "source": source,
                }
                for org, role, source, fingerprint in sorted(merged)
            ]
            self._verified_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._verified_cache_path.write_text(json.dumps(records))
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
