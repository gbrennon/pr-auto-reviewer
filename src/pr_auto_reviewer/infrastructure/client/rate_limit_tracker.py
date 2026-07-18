from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import RateLimitSnapshot

logger = logging.getLogger(__name__)


def _token_slug(token: str) -> str:
    if not token:
        return "none"
    return token[-8:]


class RateLimitTracker:
    _STORAGE_DIR = Path("/tmp/pr-auto-reviewer/rate-limits")

    def __init__(self, token_prefix: str, platform: str, role: str) -> None:
        token_slug = _token_slug(token_prefix)
        self._platform = platform
        self._role = role
        self._path = self._STORAGE_DIR / f"{platform}-{role}-{token_slug}.json"
        self.current = RateLimitSnapshot()
        self._load()

    def record(self, snapshot: RateLimitSnapshot) -> None:
        self.current = snapshot
        self._persist()
        status = snapshot.summary()
        logger.info(
            "Rate limit [%s/%s/%s]: %s",
            self._platform, self._role, snapshot.resource or "core",
            status,
        )
        if snapshot.exhausted():
            wait = snapshot.reset_seconds_from_now()
            logger.warning(
                "Rate limit [%s/%s] EXHAUSTED — reset in %ds (epoch %d)",
                self._platform, self._role, wait, snapshot.reset,
            )

    def wait_if_needed(self, min_remaining: int = 5) -> None:
        if self.current.limit == 0:
            return
        if self.current.remaining >= min_remaining:
            return
        if not self.current.exhausted() and self.current.remaining > 0:
            return
        wait = self.current.reset_seconds_from_now()
        if wait <= 0:
            wait = 60
        logger.info(
            "Rate limit [%s/%s] — waiting %ds for reset",
            self._platform, self._role, wait,
        )
        time.sleep(wait)

    def _persist(self) -> None:
        try:
            self._STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self.current.to_dict(), f)
        except OSError:
            pass

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self.current = RateLimitSnapshot(
                limit=int(data.get("limit", 0)),
                remaining=int(data.get("remaining", 0)),
                used=int(data.get("used", 0)),
                reset=int(data.get("reset", 0)),
                resource=str(data.get("resource", "")),
            )
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    def log_to_file(self, f) -> None:
        f.write(f"Rate-Limit [{self._platform}/{self._role}]: {self.current.summary()}\n")
