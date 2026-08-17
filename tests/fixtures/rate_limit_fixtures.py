"""Fixtures for RateLimitSnapshot and RateLimitTracker — captured from real API headers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import ClassVar


class RateLimitFixtures:
    """Rate-limit data captured from real Forgejo/GitHub API responses."""

    full_headers: ClassVar[dict[str, str]] = {
        "x-ratelimit-limit": "5000",
        "x-ratelimit-remaining": "4990",
        "x-ratelimit-used": "10",
        "x-ratelimit-reset": str(int(time.time()) + 3600),
        "x-ratelimit-resource": "core",
    }

    exhausted_headers: ClassVar[dict[str, str]] = {
        "x-ratelimit-limit": "5000",
        "x-ratelimit-remaining": "0",
        "x-ratelimit-used": "5000",
        "x-ratelimit-reset": str(int(time.time()) + 60),
        "x-ratelimit-resource": "core",
    }

    minimal_headers: ClassVar[dict[str, str]] = {
        "x-ratelimit-limit": "5000",
        "x-ratelimit-remaining": "2500",
    }

    empty_headers: ClassVar[dict[str, str]] = {}

    persisted_state: ClassVar[dict[str, int | str]] = {
        "limit": 5000,
        "remaining": 100,
        "used": 4900,
        "reset": 1700000000,
        "resource": "core",
    }

    # Corrupt persisted state (simulates disk corruption)
    corrupt_state: str = "not valid json {{{"

    @staticmethod
    def write_persisted_state(
        dir_path: Path, platform: str, role: str, token_suffix: str
    ) -> Path:
        """Write a valid persisted state file to *dir_path* and return its path."""
        import json

        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{platform}-{role}-{token_suffix}.json"
        file_path.write_text(json.dumps(RateLimitFixtures.persisted_state))
        return file_path

    @staticmethod
    def write_corrupt_state(
        dir_path: Path, platform: str, role: str, token_suffix: str
    ) -> Path:
        """Write a corrupt state file to *dir_path* and return its path."""
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / f"{platform}-{role}-{token_suffix}.json"
        file_path.write_text(RateLimitFixtures.corrupt_state)
        return file_path
