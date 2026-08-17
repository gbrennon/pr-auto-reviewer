"""Tracks the last-pushed timestamp per repo to skip unchanged repos."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RepoUpdateTracker:
    """Persists per-repo ``pushed_at`` timestamps to skip unchanged repos.

    Follows the same pattern as ``RateLimitStore``: JSON files under
    ``/tmp/pr-auto-reviewer/repo-updates/``, one file per repo (slugified full_name).
    """

    _STORAGE_DIR = Path("/tmp/pr-auto-reviewer/repo-updates")

    def _slugify(self, full_name: str) -> str:
        """Replace path separators with hyphens for safe filenames."""
        return full_name.replace("/", "-")

    def is_stale(self, repo_full_name: str, pushed_at: str | None) -> bool:
        """Return ``True`` if *pushed_at* differs from the last-seen value.

        Treats missing ``pushed_at`` or missing persisted file as stale
        (we re-fetch to be safe).
        """
        if pushed_at is None:
            return True

        path = self._STORAGE_DIR / f"{self._slugify(repo_full_name)}.json"
        if not path.exists():
            return True

        try:
            data = json.loads(path.read_text())
            return data.get("pushed_at") != pushed_at
        except (OSError, json.JSONDecodeError):
            logger.warning("Corrupt repo-update file for %s, treating as stale", repo_full_name)
            return True

    def mark_seen(self, repo_full_name: str, pushed_at: str) -> None:
        """Persist *pushed_at* for *repo_full_name*."""
        try:
            self._STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            path = self._STORAGE_DIR / f"{self._slugify(repo_full_name)}.json"
            with open(path, "w") as f:
                json.dump({"pushed_at": pushed_at}, f)
        except OSError as exc:
            logger.error(
                "Failed to persist repo update for %s: %s", repo_full_name, exc
            )
