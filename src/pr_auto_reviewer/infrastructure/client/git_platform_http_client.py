from __future__ import annotations

import datetime as _dt
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from pr_auto_reviewer.infrastructure.client.http_request_counter import (
    HttpRequestCounter,
)
from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import (
    RateLimitSnapshot,
)
from pr_auto_reviewer.infrastructure.client.rate_limit_tracker import (
    RateLimitTracker,
)

if TYPE_CHECKING:
    from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
    from pr_auto_reviewer.infrastructure.client.preflight_verifier import (
        PreflightVerifier,
    )
    from pr_auto_reviewer.infrastructure.client.token_resolver import TokenResolver
from pr_auto_reviewer.domain.value_objects.token_slug import TokenSlug

logger = logging.getLogger(__name__)


class GitPlatformHttpClient:
    """HTTP client for GitHub and Forgejo/Codeberg REST APIs.

    """

    def __init__(self, base_url: str, token: str, platform_mode: str = "forgejo", client_label: str = "", *, token_resolver: TokenResolver | None = None, preflight_verifier: PreflightVerifier | None = None, _verified_cache_path: Path | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._platform_mode = platform_mode
        self._role = client_label
        self._token_resolver = token_resolver
        self._preflight_verifier = preflight_verifier
        self._verified_cache_path = _verified_cache_path or Path(
            os.path.expanduser("~/.config/pr-auto-reviewer/verified-tokens.json")
        )
        self._verified_orgs: set[tuple[str, str]] = self._load_verified_cache()
        self._rate_tracker = RateLimitTracker(TokenSlug(token), platform_mode, client_label or "default")

    @property
    def base_url(self) -> str:
        return self._base_url

    def get(self, path: str, headers: dict[str, str] | None = None, *, repo: str | None = None, **params: Any) -> dict[str, Any]:
        self._rate_tracker.wait()
        url = f"{self._base_url}{path}"
        label = self._label("read")
        logger.debug("GET%s %s params=%s", label, url, params)

        request_headers = self._get_auth_header(repo)
        if headers:
            request_headers.update(headers)

        response = requests.get(url, headers=request_headers, params=params, timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            self._log_response_detail("GET", label, url, response)
            logger.error("GET%s %s failed with %s: %s", label, url, response.status_code, response.text)
            raise

        self._log_response_detail("GET", label, url, response)
        return response.json()

    def get_raw(self, path: str, headers: dict[str, str] | None = None, *, repo: str | None = None) -> str:
        self._rate_tracker.wait()
        url = f"{self._base_url}{path}"
        label = self._label("read")
        logger.debug("GET_RAW%s %s", label, url)

        request_headers = self._get_auth_header(repo)
        if headers:
            request_headers.update(headers)

        response = requests.get(url, headers=request_headers, timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            self._log_response_detail("GET_RAW", label, url, response)
            logger.error("GET_RAW%s %s failed with %s: %s", label, url, response.status_code, response.text)
            raise

        self._log_response_detail("GET_RAW", label, url, response)
        return response.text

    def post(self, path: str, body: dict[str, Any], *, repo: str | None = None) -> dict[str, Any]:
        self._rate_tracker.wait()
        url = f"{self._base_url}{path}"
        label = self._label("write")
        logger.debug("POST%s %s body_keys=%s", label, url, list(body.keys()))
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
        except requests.exceptions.HTTPError:
            self._log_response_detail("POST", label, url, response)
            logger.error("POST%s %s failed with %s: %s", label, url, response.status_code, response.text)
            raise

        self._log_response_detail("POST", label, url, response)
        return response.json()

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
        if cache_key in self._verified_orgs:
            return
        token, source_key = self._token_resolver.resolve_source(
            self._role, pr_id.repository
        )
        if not token:
            return
        self._verified_orgs.add(cache_key)
        self._save_verified_cache()
        self._preflight_verifier.verify(
            token=token,
            org=org,
            repo=pr_id.repository.split("/", 1)[1] if "/" in pr_id.repository else pr_id.repository,
            pr_number=pr_id.number,
            role=role,
            token_source=source_key,
        )

    def _capture_rate_limit(self, headers: dict[str, str]) -> None:
        if "x-ratelimit-limit" not in headers:
            return
        snapshot = RateLimitSnapshot.from_response_headers(headers)
        self._rate_tracker.record(snapshot)

    def _get_auth_header(self, repo: str | None = None) -> dict[str, str]:
        token = self._resolve_token_for_repo(repo)
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

    def _log_response_detail(self, method: str, label: str, url: str, response) -> None:
        status = response.status_code
        body_bytes = getattr(response, "content", b"")
        body_len = len(body_bytes)
        logger.debug("%s%s %s -> HTTP %d (%d bytes)", method, label, url, status, body_len)

        if logger.isEnabledFor(logging.DEBUG):
            text = response.text
            if text:
                truncated = text[:2000]
                logger.debug(
                    "%s%s %s body (%d chars):\n%s",
                    method, label, url, len(text),
                    truncated + ("..." if len(text) > 2000 else ""),
                )

        self._capture_rate_limit(getattr(response, "headers", {}))
        self._write_http_log(method, label, url, response)
        HttpRequestCounter.instance().record(self._base_url)

    def _resolve_token_for_repo(self, repo: str | None) -> str:
        """Return the token that should be used for requests scoped to
        *repo*, resolving a per-org override when one is configured."""
        if not repo or not self._token_resolver:
            return self._token
        return self._token_resolver.resolve(self._role, repo) or self._token

    def _save_verified_cache(self) -> None:
        """Persist the current ``_verified_orgs`` set to disk, merged with
        existing file contents so that writes from different client instances
        (owner/reviewer) accumulate rather than overwrite each other.

        Best-effort -- write failures are logged but never raised so that
        a transient disk issue does not block the review pipeline.
        """

        try:
            existing = self._load_verified_cache()
            merged = existing | self._verified_orgs
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
