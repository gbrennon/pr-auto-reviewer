"""PreflightVerifier statelessness test — caching lives in the client."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.client.preflight.forgejo_auth_headers import (
    ForgejoAuthHeaders,
)
from pr_auto_reviewer.infrastructure.client.preflight_verifier import (
    PreflightVerifier,
)
from tests.fakes import FakeHttpClient, FakeResponse


class TestPreflightVerifierNoCache:
    def test_verify_called_twice_sends_requests_twice(self) -> None:
        http = FakeHttpClient(responses=[
            FakeResponse(200), FakeResponse(200),
            FakeResponse(200), FakeResponse(200),
        ])
        verifier = PreflightVerifier(
            http, ForgejoAuthHeaders(), "https://api.example.com", "forgejo"
        )
        verifier.verify("tok", "org", "repo", 1)
        verifier.verify("tok", "org", "repo", 1)
        assert len(http.calls) == 4
