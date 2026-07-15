"""PreflightVerifier statelessness test — caching lives in the client."""

from __future__ import annotations

from tests.fakes.preflight_fakes import FakeHttpCaller, FakeResponse

from pr_auto_reviewer.infrastructure.client.preflight_verifier import (
    PreflightVerifier,
)

class TestNoCaching:
    def test_called_twice_makes_calls_twice(self) -> None:
        fake_get = FakeHttpCaller(responses=[FakeResponse(200), FakeResponse(200)])
        fake_post = FakeHttpCaller(responses=[FakeResponse(200), FakeResponse(200)])
        verifier = PreflightVerifier(
            "https://api.example.com", "forgejo",
            _http_get=fake_get, _http_post=fake_post,
        )
        verifier.verify("tok", "org", "repo", 1)
        verifier.verify("tok", "org", "repo", 1)
        assert len(fake_get.calls) == 2
        assert len(fake_post.calls) == 2
