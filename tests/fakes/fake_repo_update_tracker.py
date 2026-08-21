"""Fake RepoUpdateTracker for tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FakeRepoUpdateTracker:
    """Fake RepoUpdateTracker that tracks calls without performing file I/O."""

    _STORAGE_DIR = Path("/tmp/pr-auto-reviewer/repo-updates")

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self.is_stale_calls: list[tuple[str, str | None]] = []
        self.mark_seen_calls: list[tuple[str, str]] = []

    def _slugify(self, full_name: str) -> str:
        """Replace path separators with hyphens for safe filenames."""
        return full_name.replace("/", "-")

    def is_stale(self, repo_full_name: str, pushed_at: str | None) -> bool:
        """Return True if pushed_at differs from the last-seen value."""
        self.is_stale_calls.append((repo_full_name, pushed_at))
        if pushed_at is None:
            return True
        if repo_full_name not in self._data:
            return True
        return self._data[repo_full_name] != pushed_at

    def mark_seen(self, repo_full_name: str, pushed_at: str) -> None:
        """Persist pushed_at for repo_full_name."""
        self.mark_seen_calls.append((repo_full_name, pushed_at))
        self._data[repo_full_name] = pushed_at