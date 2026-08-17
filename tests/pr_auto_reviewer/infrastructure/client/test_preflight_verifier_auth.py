"""PreflightVerifier auth check tests."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from pr_auto_reviewer.domain.exceptions.preflight_verification_error import (
    PreflightVerificationError,
)
from pr_auto_reviewer.infrastructure.client.preflight.forgejo_auth_headers import (
    ForgejoAuthHeaders,
)
from pr_auto_reviewer.infrastructure.client.preflight_verifier import (
    PreflightVerifier,
)
from tests.fakes import FakeHttpClient, FakeResponse


class FailingGetClient:
    def get(self, path: str, *, headers: dict[str, str]) -> None:
        raise requests.ConnectionError("connection refused")

    def post(self, path: str, *, headers: dict[str, str], json: dict[str, Any]) -> FakeResponse:
        return FakeResponse(200)


class TestPreflightVerifierAuth:
    def test_verify_passes_when_auth_returns_200(self) -> None:
        http = FakeHttpClient(responses=[FakeResponse(200)])
        verifier = PreflightVerifier(
            http, ForgejoAuthHeaders(), "https://api.example.com", "forgejo"
        )
        verifier.verify("tok", "my-org", "my-repo", 1, "owner")
        assert http.calls[0]["url"] == "/user"

    def test_verify_raises_when_auth_returns_401(self) -> None:
        http = FakeHttpClient(responses=[FakeResponse(401)])
        verifier = PreflightVerifier(
            http, ForgejoAuthHeaders(), "https://api.example.com", "forgejo"
        )
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1, "owner")
        assert exc.value.http_status == 401
        assert exc.value.step == "auth"

    def test_verify_raises_when_auth_request_fails(self) -> None:
        verifier = PreflightVerifier(
            FailingGetClient(), ForgejoAuthHeaders(),
            "https://api.example.com", "forgejo",
        )
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1)
        assert exc.value.http_status == 0
        assert exc.value.step == "auth"
