"""RateLimitTracker — composed orchestrator for rate-limit tracking.

Delegates persistence to ``RateLimitStore`` and back-off to
``RateLimitWaiter``.
"""

from __future__ import annotations

import logging
from typing import IO

from pr_auto_reviewer.domain.value_objects.token_slug import TokenSlug
from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import RateLimitSnapshot
from pr_auto_reviewer.infrastructure.client.rate_limit_tracker.rate_limit_store import (
    RateLimitStore,
)
from pr_auto_reviewer.infrastructure.client.rate_limit_tracker.rate_limit_waiter import (
    RateLimitWaiter,
)

logger = logging.getLogger(__name__)


class RateLimitTracker:
    """Tracks GitHub/Forgejo API rate limits with disk-persisted state.

    Composes ``RateLimitStore`` for persistence and ``RateLimitWaiter``
    for back-off logic.
    """


    def __init__(self, token_slug: TokenSlug, platform: str, role: str) -> None:
        self._platform = platform
        self._role = role
        path = RateLimitStore._STORAGE_DIR / f"{platform}-{role}-{token_slug}.json"
        self._store = RateLimitStore(path)
        self._waiter = RateLimitWaiter()
        self.current = self._store.load()

    def log_to_file(self, f: IO[str]) -> None:
        """Write a one-line summary to *f*."""
        f.write(
            f"Rate-Limit [{self._platform}/{self._role}]: {self.current.summary()}\n"
        )

    def record(self, snapshot: RateLimitSnapshot) -> None:
        """Record a new rate-limit snapshot and persist it to disk."""
        self.current = snapshot
        self._store.save(snapshot)
        status = snapshot.summary()
        logger.info(
            "Rate limit [%s/%s/%s]: %s",
            self._platform,
            self._role,
            snapshot.resource or "core",
            status,
        )
        if snapshot.exhausted():
            wait_seconds = snapshot.reset_seconds_from_now()
            logger.warning(
                "Rate limit [%s/%s] EXHAUSTED — reset in %ds (epoch %d)",
                self._platform,
                self._role,
                wait_seconds,
                snapshot.reset,
            )

    def wait(self, min_remaining: int = 5) -> None:
        """Block until the rate-limit window resets, if the current
        state indicates waiting is necessary.
        """
        self._waiter.wait(self.current, self._platform, self._role, min_remaining)
