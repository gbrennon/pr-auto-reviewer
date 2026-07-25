"""TokenVerifier — runs preflight once per token and caches verified orgs.

Preflight verifies two things for each token:

1. **Auth validity** — ``GET /user`` must return 200.  A 401 means the
   token is expired, revoked, or never existed.
2. **Write access** — ``POST …/requested_reviewers`` with an empty
   reviewer list must return 200/201 or 422.  A 401 or 403 means the
   token lacks write permission on the target repo.

Both checks are side-effect-free — no reviewer is actually requested.
For GitHub the ``Accept: application/vnd.github+json`` header is
sent on write-access checks.  For Codeberg/Forgejo the ``token`` prefix
is used instead of ``Bearer`` and no ``Accept`` header is needed.

Verified ``(org, role)`` pairs are cached in memory for the current
process.  When *persist* is ``True`` they are also written to
``~/.config/pr-auto-reviewer/verified-tokens.json`` so subsequent
invocations skip verification entirely.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from pr_auto_reviewer.application.ports.outbound.token_verifier_port import (
    TokenVerifierPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)

logger = logging.getLogger(__name__)


class TokenVerifier(TokenVerifierPort):
    """Verifies owner and reviewer tokens before a review.

    Args:
        owner_client: HTTP client wired with the owner token.
        reviewer_client: HTTP client wired with the reviewer token.
        persist: When ``True`` verified pairs are persisted to disk
            so preflight runs only once across invocations.
    """

    def _load(self) -> set[tuple[str, str]]:
        if not self._store_path.exists():
            return set()
        try:
            data = json.loads(self._store_path.read_text())
            return {tuple(pair) for pair in data}
        except (json.JSONDecodeError, OSError):
            return set()

    def __init__(
        self,
        owner_client: GitPlatformHttpClient,
        reviewer_client: GitPlatformHttpClient,
        *,
        persist: bool = True,
        forgejo_owner_client: GitPlatformHttpClient | None = None,
        forgejo_reviewer_client: GitPlatformHttpClient | None = None,
        _store_path: Path | None = None,
    ) -> None:
        self._owner_client = owner_client
        self._reviewer_client = reviewer_client
        self._forgejo_owner_client = forgejo_owner_client
        self._forgejo_reviewer_client = forgejo_reviewer_client
        self._persist = persist
        self._store_path = (
            _store_path
            if _store_path is not None
            else Path(
                os.path.expanduser("~/.config/pr-auto-reviewer/verified-tokens.json")
            )
        )
        self._verified: set[tuple[str, str]] = self._load() if persist else set()

    def _save(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        self._store_path.write_text(json.dumps(sorted(self._verified)))

    def verify(self, pr_id: PullRequestId) -> None:
        org = pr_id.repository.split("/", 1)[0]
        if not org:
            return

        owner_client = self._owner_client
        reviewer_client = self._reviewer_client
        if org.startswith("forgejo:") and self._forgejo_owner_client is not None:
            org = org.split(":", 1)[1]  # strip prefix for cache key
            owner_client = self._forgejo_owner_client
            reviewer_client = self._forgejo_reviewer_client

        for role, client in [
            ("owner", owner_client),
            ("reviewer", reviewer_client),
        ]:
            cache_key = (org, role)
            if cache_key in self._verified:
                continue

            client.verify_token_for_pr(pr_id)
            self._verified.add(cache_key)
            if self._persist:
                self._save()
            logger.info("TokenVerifier: %s/%s verified and cached", org, role)
