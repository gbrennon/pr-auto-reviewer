"""PreflightVerifier write-access check tests."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from tests.fakes.preflight_fakes import FakeHttpClient, FakeResponse

from pr_auto_reviewer.domain.exceptions.preflight_verification_error import (
    PreflightVerificationError,
)
from pr_auto_reviewer.infrastructure.client.preflight.forgejo_auth_headers import (
    ForgejoAuthHeaders,
)
from pr_auto_reviewer.infrastructure.client.preflight_verifier import (
    PreflightVerifier,
)


class FailingPostClient:
    def get(self, path: str, *, headers: dict[str, str]) -> FakeResponse:
        return FakeResponse(200)

    def post(self, path: str, *, headers: dict[str, str], json: dict[str, Any]) -> None:
        raise requests.ConnectionError("timeout")


class TestPreflightVerifierWriteAccess:
    def test_verify_passes_when_write_check_returns_200(self) -> None:
        http = FakeHttpClient(responses=[FakeResponse(200), FakeResponse(200)])
        verifier = PreflightVerifier(
            http, ForgejoAuthHeaders(), "https://api.example.com", "forgejo"
        )
        verifier.verify("tok", "my-org", "my-repo", 42, "reviewer")
        assert "/repos/my-org/my-repo/pulls/42/requested_reviewers" in http.calls[1]["url"]

    def test_verify_passes_when_write_check_returns_422(self) -> None:
        http = FakeHttpClient(responses=[FakeResponse(200), FakeResponse(422)])
        verifier = PreflightVerifier(
            http, ForgejoAuthHeaders(), "https://api.example.com", "forgejo"
        )
        verifier.verify("tok", "my-org", "my-repo", 1)

    def test_verify_raises_when_write_check_returns_403(self) -> None:
        http = FakeHttpClient(responses=[FakeResponse(200), FakeResponse(403)])
        verifier = PreflightVerifier(
            http, ForgejoAuthHeaders(), "https://api.example.com", "forgejo"
        )
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1)
        assert exc.value.http_status == 403
        assert exc.value.step == "write_access"

    def test_verify_raises_when_write_check_returns_401(self) -> None:
        http = FakeHttpClient(responses=[FakeResponse(200), FakeResponse(401)])
        verifier = PreflightVerifier(
            http, ForgejoAuthHeaders(), "https://api.example.com", "forgejo"
        )
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1)
        assert exc.value.http_status == 401
        assert exc.value.step == "write_access"

    def test_verify_raises_when_write_check_request_fails(self) -> None:
        verifier = PreflightVerifier(
            FailingPostClient(), ForgejoAuthHeaders(),
            "https://api.example.com", "forgejo",
        )
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1)
        assert exc.value.http_status == 0
        assert exc.value.step == "write_access"
