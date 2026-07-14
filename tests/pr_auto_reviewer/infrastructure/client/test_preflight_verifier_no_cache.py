"""PreflightVerifier statelessness test — caching lives in the client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pr_auto_reviewer.infrastructure.client.preflight_verifier import (
    PreflightVerifier,
)


@dataclass
class FakeResponse:
    status_code: int

    def raise_for_status(self) -> None:
        pass


def _patch_get(monkeypatch, status: int = 200) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_get(url: str, headers: dict, timeout: int, **kwargs: Any) -> FakeResponse:
        calls.append({"url": url, "headers": dict(headers), "timeout": timeout})
        return FakeResponse(status)

    monkeypatch.setattr("requests.get", fake_get)
    return calls


def _patch_post(monkeypatch, status: int = 200) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_post(url, headers, json, timeout, **kwargs):
        calls.append({"url": url, "headers": dict(headers), "json": json, "timeout": timeout})
        return FakeResponse(status)

    monkeypatch.setattr("requests.post", fake_post)
    return calls


class TestNoCaching:
    def test_called_twice_makes_calls_twice(self, monkeypatch):
        get_calls = _patch_get(monkeypatch, 200)
        post_calls = _patch_post(monkeypatch, 200)
        verifier = PreflightVerifier("https://api.example.com", "forgejo")
        verifier.verify("tok", "org", "repo", 1)
        verifier.verify("tok", "org", "repo", 1)
        assert len(get_calls) == 2
        assert len(post_calls) == 2
