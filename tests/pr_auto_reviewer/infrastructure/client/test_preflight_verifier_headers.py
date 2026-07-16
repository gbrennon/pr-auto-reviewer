"""PreflightVerifier platform-specific header tests."""

from __future__ import annotations

from tests.fakes.preflight_fakes import FakeHttpClient, FakeResponse

from pr_auto_reviewer.infrastructure.client.preflight.forgejo_auth_headers import (
    ForgejoAuthHeaders,
)
from pr_auto_reviewer.infrastructure.client.preflight.github_auth_headers import (
    GitHubAuthHeaders,
)
from pr_auto_reviewer.infrastructure.client.preflight_verifier import (
    PreflightVerifier,
)


class TestPreflightVerifierHeaders:
    def test_verify_uses_bearer_auth_for_github(self) -> None:
        http = FakeHttpClient(responses=[FakeResponse(200)])
        verifier = PreflightVerifier(
            http, GitHubAuthHeaders(), "https://api.example.com", "github"
        )
        verifier.verify("ghp_token", "o", "r", 1)
        assert http.calls[0]["headers"]["Authorization"] == "Bearer ghp_token"

    def test_verify_uses_token_auth_for_forgejo(self) -> None:
        http = FakeHttpClient(responses=[FakeResponse(200)])
        verifier = PreflightVerifier(
            http, ForgejoAuthHeaders(), "https://api.example.com", "forgejo"
        )
        verifier.verify("fj_token", "o", "r", 1)
        assert http.calls[0]["headers"]["Authorization"] == "token fj_token"

    def test_verify_sends_accept_header_for_github_write_check(self) -> None:
        http = FakeHttpClient(responses=[FakeResponse(200), FakeResponse(200)])
        verifier = PreflightVerifier(
            http, GitHubAuthHeaders(), "https://api.example.com", "github"
        )
        verifier.verify("t", "o", "r", 1)
        assert http.calls[1]["headers"]["Accept"] == "application/vnd.github.v3+json"

    def test_verify_sends_no_accept_header_for_forgejo_write_check(self) -> None:
        http = FakeHttpClient(responses=[FakeResponse(200), FakeResponse(200)])
        verifier = PreflightVerifier(
            http, ForgejoAuthHeaders(), "https://api.example.com", "forgejo"
        )
        verifier.verify("t", "o", "r", 1)
        assert "Accept" not in http.calls[1]["headers"]
