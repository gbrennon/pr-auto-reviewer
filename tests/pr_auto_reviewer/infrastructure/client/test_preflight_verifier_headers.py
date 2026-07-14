"""PreflightVerifier platform-specific header tests."""

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


def _make_verifier(platform: str) -> PreflightVerifier:
    return PreflightVerifier("https://api.example.com", platform)


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


class TestPlatformHeaders:
    def test_github_uses_bearer_auth(self, monkeypatch):
        calls = _patch_get(monkeypatch, 200)
        _patch_post(monkeypatch, 200)
        verifier = _make_verifier("github")
        verifier.verify("ghp_token", "o", "r", 1)
        assert calls[0]["headers"]["Authorization"] == "Bearer ghp_token"

    def test_forgejo_uses_token_auth(self, monkeypatch):
        calls = _patch_get(monkeypatch, 200)
        _patch_post(monkeypatch, 200)
        verifier = _make_verifier("forgejo")
        verifier.verify("fj_token", "o", "r", 1)
        assert calls[0]["headers"]["Authorization"] == "token fj_token"

    def test_github_write_check_sends_accept_header(self, monkeypatch):
        _patch_get(monkeypatch, 200)
        post_calls = _patch_post(monkeypatch, 200)
        verifier = _make_verifier("github")
        verifier.verify("t", "o", "r", 1)
        assert post_calls[0]["headers"]["Accept"] == "application/vnd.github.v3+json"

    def test_forgejo_write_check_no_github_accept_header(self, monkeypatch):
        _patch_get(monkeypatch, 200)
        post_calls = _patch_post(monkeypatch, 200)
        verifier = _make_verifier("forgejo")
        verifier.verify("t", "o", "r", 1)
        assert "Accept" not in post_calls[0]["headers"]
