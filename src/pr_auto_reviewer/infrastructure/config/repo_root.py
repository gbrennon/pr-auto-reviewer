"""Finds the repository root directory."""

from __future__ import annotations

from pathlib import Path


class RepoRoot:
    """Locates the repository root."""

    @classmethod
    def path(cls) -> Path:
        return Path(__file__).parent.parent.parent.parent.parent
