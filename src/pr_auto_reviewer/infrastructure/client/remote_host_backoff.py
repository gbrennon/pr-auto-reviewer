from __future__ import annotations

import logging
import time
from collections.abc import Callable
from urllib.parse import urlsplit

from pr_auto_reviewer.domain.exceptions.remote_operation_quarantined_error import (
    RemoteOperationQuarantinedError,
)

logger = logging.getLogger(__name__)


class RemoteHostBackoff:
    """Throttle remote operations with progressive delay and quarantine."""

    def __init__(
        self,
        *,
        threshold: int = 3,
        interval_seconds: float = 60.0,
        interval_increment_seconds: float = 60.0,
        quarantine_seconds: float = 3600.0,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if threshold < 1:
            raise ValueError("threshold must be positive")
        if interval_seconds < 0:
            raise ValueError("interval_seconds must not be negative")
        if interval_increment_seconds < 0:
            raise ValueError(
                "interval_increment_seconds must not be negative"
            )
        if quarantine_seconds < 0:
            raise ValueError("quarantine_seconds must not be negative")
        self._threshold = threshold
        self._interval_seconds = interval_seconds
        self._interval_increment_seconds = interval_increment_seconds
        self._quarantine_seconds = quarantine_seconds
        self._clock = clock
        self._sleeper = sleeper
        self._states: dict[str, tuple[int, float | None, float | None]] = {}

    @classmethod
    def host_from_url(cls, value: str) -> str | None:
        """Extract a normalized hostname from an API or clone URL."""
        text = value.strip()
        if not text:
            return None
        parsed = urlsplit(text if "://" in text else f"//{text}")
        if parsed.hostname:
            return cls._normalise_key(parsed.hostname)
        if "://" in text:
            return None
        if len(text) > 1 and text[1] == ":" and text[0].isalpha():
            return None
        prefix = text.split("/", 1)[0]
        if ":" not in prefix:
            return cls._normalise_key(prefix)
        host = prefix.rsplit(":", 1)[0].rsplit("@", 1)[-1]
        if host.startswith("/"):
            return None
        return cls._normalise_key(host)

    def before_operation(self, *keys: str | None) -> None:
        """Wait for retry delay or reject an operation in quarantine."""
        for key in keys:
            normalized = self._normalise_key(key)
            if normalized is None:
                continue
            state = self._states.get(normalized)
            if state is None:
                continue
            failures, retry_at, quarantine_until = state
            now = self._clock()
            if quarantine_until is not None:
                remaining = quarantine_until - now
                if remaining > 0:
                    logger.warning(
                        "Remote operation %s is quarantined; "
                        "retrying after %.1f seconds",
                        normalized,
                        remaining,
                    )
                    raise RemoteOperationQuarantinedError(
                        normalized, remaining,
                    )
                self._states[normalized] = (0, None, None)
                continue
            if retry_at is None:
                continue
            remaining = retry_at - now
            if remaining <= 0:
                self._states[normalized] = (failures, None, None)
                continue
            logger.info(
                "Remote operation %s is backing off; waiting %.1f seconds",
                normalized,
                remaining,
            )
            self._sleeper(remaining)
            self._states[normalized] = (failures, None, None)

    def record_failure(self, key: str | None) -> None:
        """Record one failure and schedule progressive retry protection."""
        normalized = self._normalise_key(key)
        if normalized is None:
            return
        previous, _, quarantine_until = self._states.get(
            normalized, (0, None, None),
        )
        now = self._clock()
        if quarantine_until is not None and quarantine_until <= now:
            previous = 0
        failures = previous + 1
        retry_at = now + self._interval_seconds + (
            (failures - 1) * self._interval_increment_seconds
        )
        quarantine = (
            now + self._quarantine_seconds
            if failures >= self._threshold and self._quarantine_seconds > 0
            else None
        )
        self._states[normalized] = (failures, retry_at, quarantine)

    def record_success(self, key: str | None) -> None:
        """Reset the failure streak for one remote operation key."""
        normalized = self._normalise_key(key)
        if normalized is not None:
            self._states.pop(normalized, None)

    @staticmethod
    def _normalise_key(key: str | None) -> str | None:
        if key is None:
            return None
        normalized = key.strip().lower().rstrip(".")
        return normalized or None
