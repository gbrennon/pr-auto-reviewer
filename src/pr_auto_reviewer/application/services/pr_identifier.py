"""Derive a stable ``owner/repo#pr`` identifier from a review clone path."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_PR_PATTERN = re.compile(r"/repos/([^/]+)_([^/]+)_(\d+)$")


class PRIdentifier:
    """Normalize clone directories into the platform PR identity."""

    @staticmethod
    def derive(repo_path: Path | str | None) -> str:
        """Return ``owner/repo#pr`` for a clone path, or a best-effort label."""
        if repo_path is None:
            return "unknown"
        path_str = str(repo_path)
        match = _REPO_PR_PATTERN.search(path_str)
        if match:
            return f"{match.group(1)}/{match.group(2)}#{match.group(3)}"
        return path_str.rsplit("/", 1)[-1]
