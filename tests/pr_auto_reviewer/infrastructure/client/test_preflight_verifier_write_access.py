"""PreflightVerifier write-access check tests."""

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


class TestWriteAccessCheck:
    def test_200_passes(self, monkeypatch):
        _patch_get(monkeypatch, 200)
        post_calls = _patch_post(monkeypatch, 200)
        verifier = _make_verifier()
        verifier.verify("tok", "my-org", "my-repo", 42, "reviewer")
        assert "/repos/my-org/my-repo/pulls/42/requested_reviewers" in post_calls[0]["url"]

    def test_422_passes(self, monkeypatch):
        _patch_get(monkeypatch, 200)
        _patch_post(monkeypatch, 422)
        verifier = _make_verifier()
        verifier.verify("tok", "my-org", "my-repo", 1)

    def test_403_raises(self, monkeypatch):
        _patch_get(monkeypatch, 200)
        _patch_post(monkeypatch, 403)
        verifier = _make_verifier()
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1)
        assert exc.value.http_status == 403
        assert exc.value.step == "write_access"

    def test_401_raises(self, monkeypatch):
        _patch_get(monkeypatch, 200)
        _patch_post(monkeypatch, 401)
        verifier = _make_verifier()
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1)
        assert exc.value.http_status == 401
        assert exc.value.step == "write_access"

    def test_connection_error_raises(self, monkeypatch):
        _patch_get(monkeypatch, 200)

        def raise_err(*a, **kw):
            raise requests.ConnectionError("timeout")

        monkeypatch.setattr("requests.post", raise_err)
        verifier = _make_verifier()
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1)
        assert exc.value.http_status == 0
        assert exc.value.step == "write_access"
