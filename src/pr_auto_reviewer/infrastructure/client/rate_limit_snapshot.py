from __future__ import annotations

import time


class RateLimitSnapshot:
    def __init__(
        self,
        limit: int = 0,
        remaining: int = 0,
        used: int = 0,
        reset: int = 0,
        resource: str = "",
    ) -> None:
        self.limit = limit
        self.remaining = remaining
        self.used = used
        self.reset = reset
        self.resource = resource

    @staticmethod
    def from_response_headers(headers: dict[str, str]) -> RateLimitSnapshot:
        return RateLimitSnapshot(
            limit=int(headers.get("x-ratelimit-limit", 0)),
            remaining=int(headers.get("x-ratelimit-remaining", 0)),
            used=int(headers.get("x-ratelimit-used", 0)),
            reset=int(headers.get("x-ratelimit-reset", 0)),
            resource=headers.get("x-ratelimit-resource", ""),
        )

    def exhausted(self) -> bool:
        return self.remaining == 0 and self.limit > 0

    def reset_seconds_from_now(self) -> int:
        if self.reset == 0:
            return 0
        return max(0, self.reset - int(time.time()))

    def summary(self) -> str:
        parts = [f"remaining={self.remaining}/{self.limit}"]
        if self.used:
            parts.append(f"used={self.used}")
        if self.resource:
            parts.append(f"resource={self.resource}")
        if self.reset:
            wait = self.reset_seconds_from_now()
            parts.append(f"reset_in={wait}s")
        return " ".join(parts)

    def to_dict(self) -> dict[str, int | str]:
        return {
            "limit": self.limit,
            "remaining": self.remaining,
            "used": self.used,
            "reset": self.reset,
            "resource": self.resource,
        }
