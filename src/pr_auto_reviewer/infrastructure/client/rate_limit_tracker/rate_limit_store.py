"""Storage-backed persistence for rate-limit snapshots."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import RateLimitSnapshot

logger = logging.getLogger(__name__)


class RateLimitStore:
    """Persists rate-limit snapshots to JSON files on disk.

    Writes are throttled — ``save()`` is a no-op if called within
    ``_SAVE_COOLDOWN`` seconds of the last actual write, preventing
    redundant synchronous disk I/O on every API response.
    """

    _STORAGE_DIR = Path("/tmp/pr-auto-reviewer/rate-limits")
    _SAVE_COOLDOWN = 5.0  # seconds between disk writes

    def __init__(self, path: Path) -> None:
        self._path = path
        self._last_write: float = 0.0

    def load(self) -> RateLimitSnapshot:
        """Load the last persisted snapshot from disk, or a default empty one."""
        if not self._path.exists():
            return RateLimitSnapshot()
        try:
            data = json.loads(self._path.read_text())
            return RateLimitSnapshot(
                limit=int(data.get("limit", 0)),
                remaining=int(data.get("remaining", 0)),
                used=int(data.get("used", 0)),
                reset=int(data.get("reset", 0)),
                resource=str(data.get("resource", "")),
            )
        except (OSError, json.JSONDecodeError, ValueError):
            return RateLimitSnapshot()

    def save(self, snapshot: RateLimitSnapshot) -> None:
        """Persist *snapshot* to disk, skipping writes within the cooldown window."""
        now = time.monotonic()
        if now - self._last_write < self._SAVE_COOLDOWN:
            return
        self._force_save(snapshot)

    def save_urgent(self, snapshot: RateLimitSnapshot) -> None:
        """Persist *snapshot* to disk immediately, bypassing the cooldown."""
        self._force_save(snapshot)

    def _force_save(self, snapshot: RateLimitSnapshot) -> None:
        """Unconditional disk write. Logs I/O errors if write fails."""
        try:
            self._STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(snapshot.to_dict(), f)
            self._last_write = time.monotonic()
        except OSError as exc:
            logger.error("Failed to persist rate limit snapshot to %s: %s", self._path, exc)
