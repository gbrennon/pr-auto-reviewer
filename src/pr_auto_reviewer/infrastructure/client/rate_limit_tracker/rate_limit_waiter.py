"""Rate-limit wait / back-off logic."""

from __future__ import annotations

import logging
import time

from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import RateLimitSnapshot

logger = logging.getLogger(__name__)


class RateLimitWaiter:
    """Decides whether to sleep until a rate-limit window resets."""

    def wait(
        self,
        snapshot: RateLimitSnapshot,
        platform: str,
        role: str,
        min_remaining: int = 5,
    ) -> None:
        """Block until the rate-limit window resets, if needed."""
        if snapshot.limit == 0:
            return
        if snapshot.remaining >= min_remaining:
            return
        if not snapshot.exhausted() and snapshot.remaining > 0:
            return
        wait_seconds = snapshot.reset_seconds_from_now()
        if wait_seconds <= 0:
            wait_seconds = 60
        logger.info(
            "Rate limit [%s/%s] — waiting %ds for reset",
            platform,
            role,
            wait_seconds,
        )
        time.sleep(wait_seconds)
