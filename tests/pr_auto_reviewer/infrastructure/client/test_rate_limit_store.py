"""Tests for RateLimitStore cooldown behaviour (Bug 5 fix)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import RateLimitSnapshot
from pr_auto_reviewer.infrastructure.client.rate_limit_tracker.rate_limit_store import (
    RateLimitStore,
)


class TestRateLimitStore:
    def test_save_throttled_within_cooldown(self, tmp_path: Path, monkeypatch) -> None:
        """Rapid save() calls within the cooldown window only write once.

        save_urgent() must always persist regardless of cooldown state.
        """
        store_path = tmp_path / "rate_limits.json"
        store = RateLimitStore(store_path)

        fake_now = 100.0
        monkeypatch.setattr(time, "monotonic", lambda: fake_now)

        # First save → must write (last_write=0 → 100 s elapsed > 5 s cooldown)

        store.save(RateLimitSnapshot(remaining=4999, limit=5000, resource="core"))
        assert store_path.exists()
        assert _json_at(store_path)["remaining"] == 4999

        # Advance clock by 1 s — still well inside the 5 s cooldown
        fake_now = 101.0
        store.save(RateLimitSnapshot(remaining=4998, limit=5000, resource="core"))
        # File content MUST still be the *first* write — cooldown suppressed the second
        assert _json_at(store_path)["remaining"] == 4999, (
            "Second save() within cooldown should be a no-op; "
            "file still shows first write's remaining=4999"
        )

        # save_urgent must always write, even within the cooldown
        store.save_urgent(RateLimitSnapshot(remaining=0, limit=5000, resource="core"))
        assert _json_at(store_path)["remaining"] == 0, (
            "save_urgent() must persist immediately regardless of cooldown"
        )


def _json_at(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())  # type: ignore[no-any-return]
