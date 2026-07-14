"""PreflightVerifier auth check tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import requests

from pr_auto_reviewer.domain.exceptions.preflight_verification_error import (
    PreflightVerificationError,
)
from pr_auto_reviewer.infrastructure.client.preflight_verifier import (
    PreflightVerifier,
)


@dataclass
class FakeResponse:
    status_code: int

    def raise_for_status(self) -> None:
        pass


def _make_verifier(platform: str = "forgejo") -> PreflightVerifier:
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


class TestAuthCheck:
    def test_200_passes(self, monkeypatch):
        calls = _patch_get(monkeypatch, 200)
        _patch_post(monkeypatch, 200)
        verifier = _make_verifier()
        verifier.verify("tok", "my-org", "my-repo", 1, "owner")
        assert calls[0]["url"] == "https://api.example.com/user"

    def test_401_raises(self, monkeypatch):
        _patch_get(monkeypatch, 401)
        _patch_post(monkeypatch, 200)
        verifier = _make_verifier()
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1, "owner")
        assert exc.value.http_status == 401
        assert exc.value.step == "auth"
        assert exc.value.org == "my-org"
        assert exc.value.role == "owner"

    def test_connection_error_raises(self, monkeypatch):
        def raise_err(*a, **kw):
            raise requests.ConnectionError("connection refused")

        monkeypatch.setattr("requests.get", raise_err)
        _patch_post(monkeypatch, 200)
        verifier = _make_verifier()
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1)
        assert exc.value.http_status == 0
        assert exc.value.step == "auth"
