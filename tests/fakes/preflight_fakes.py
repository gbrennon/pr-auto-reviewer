"""Fake HTTP callers for PreflightVerifier tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass
class FakeResponse:
    status_code: int

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


@dataclass
class FakeHttpCaller:
    responses: list[FakeResponse] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> FakeResponse:
        self.calls.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return self.responses.pop(0) if self.responses else FakeResponse(200)
