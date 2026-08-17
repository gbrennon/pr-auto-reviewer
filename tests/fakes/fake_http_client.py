"""Fake HTTP client for PreflightVerifier tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tests.fakes.fake_response import FakeResponse


@dataclass
class FakeHttpClient:
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

    def get(self, path: str, *, headers: dict[str, str]) -> FakeResponse:
        self.calls.append({"url": path, "headers": headers})
        return self.responses.pop(0) if self.responses else FakeResponse(200)

    def post(
        self, path: str, *, headers: dict[str, str], json: dict[str, Any]
    ) -> FakeResponse:
        self.calls.append({"url": path, "headers": headers, "json": json})
        return self.responses.pop(0) if self.responses else FakeResponse(200)