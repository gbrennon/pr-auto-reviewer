"""Storage-backed persistence for rate-limit snapshots."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import RateLimitSnapshot

logger = logging.getLogger(__name__)


class RateLimitStore:
    """Persists rate-limit snapshots to JSON files on disk."""

    _STORAGE_DIR = Path("/tmp/pr-auto-reviewer/rate-limits")

    def __init__(self, path: Path) -> None:
        self._path = path

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
        """Persist *snapshot* to disk. Logs I/O errors if write fails."""
        try:
            self._STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(snapshot.to_dict(), f)
        except OSError as exc:
            logger.error("Failed to persist rate limit snapshot to %s: %s", self._path, exc)
