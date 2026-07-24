"""HttpRequestCounter - shared counter tracking HTTP requests per domain.

Module-level singleton shared across all ``GitPlatformHttpClient``
instances so callers in the presentation layer can log a summary after
each review cycle.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from threading import Lock
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class HttpRequestCounter:
    """Thread-safe counter tracking HTTP requests grouped by hostname.

    ``GitPlatformHttpClient`` records every request in
    ``_log_response_detail``.  Presentation-layer callers (CLI runner,
    polling daemon) call ``log_summary`` after each review and
    ``reset`` before the next one so every review gets its own tally.
    """

    _instance: HttpRequestCounter | None = None
    _lock: Lock = Lock()

    def __init__(self) -> None:
        self._counts: dict[str, int] = defaultdict(int)
        self._total: int = 0

    @classmethod
    def instance(cls) -> HttpRequestCounter:
        """Return the process-wide singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def record(self, base_url: str) -> None:
        """Increment the counter for the hostname extracted from *base_url*.

        Extracts just the netloc so ``https://codeberg.org/api/v1``
        registers as ``codeberg.org``.
        """
        hostname = urlparse(base_url).hostname or base_url
        with self._lock:
            self._counts[hostname] += 1
            self._total += 1

    def log_summary(self) -> None:
        """Log a DEBUG-level summary of recorded requests grouped by hostname.

        When the counter is empty the summary reports "No HTTP requests
        made" so the caller can verify the pre-review gate worked.
        """
        with self._lock:
            counts = dict(self._counts)
            total = self._total

        if not counts:
            logger.debug("HTTP Request Summary: No HTTP requests made.")
            return

        logger.debug("HTTP Request Summary (%d total):", total)
        for hostname, count in sorted(counts.items()):
            logger.debug("  %-40s %d requests", hostname, count)

    def reset(self) -> None:
        """Zero all counters for the next review cycle."""
        with self._lock:
            self._counts.clear()
            self._total = 0
