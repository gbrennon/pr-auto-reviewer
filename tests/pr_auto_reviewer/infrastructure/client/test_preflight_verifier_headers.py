"""PreflightVerifier platform-specific header tests."""

from __future__ import annotations

from tests.fakes.preflight_fakes import FakeHttpCaller, FakeResponse

from pr_auto_reviewer.infrastructure.client.preflight_verifier import (
    PreflightVerifier,
)

class TestPlatformHeaders:
    def test_github_uses_bearer_auth(self) -> None:
        fake_get = FakeHttpCaller(responses=[FakeResponse(200)])
        fake_post = FakeHttpCaller(responses=[FakeResponse(200)])
        verifier = PreflightVerifier(
            "https://api.example.com", "github",
            _http_get=fake_get, _http_post=fake_post,
        )
        verifier.verify("ghp_token", "o", "r", 1)
        assert fake_get.calls[0]["headers"]["Authorization"] == "Bearer ghp_token"

    def test_forgejo_uses_token_auth(self) -> None:
        fake_get = FakeHttpCaller(responses=[FakeResponse(200)])
        fake_post = FakeHttpCaller(responses=[FakeResponse(200)])
        verifier = PreflightVerifier(
            "https://api.example.com", "forgejo",
            _http_get=fake_get, _http_post=fake_post,
        )
        verifier.verify("fj_token", "o", "r", 1)
        assert fake_get.calls[0]["headers"]["Authorization"] == "token fj_token"

    def test_github_write_check_sends_accept_header(self) -> None:
        fake_get = FakeHttpCaller(responses=[FakeResponse(200)])
        fake_post = FakeHttpCaller(responses=[FakeResponse(200)])
        verifier = PreflightVerifier(
            "https://api.example.com", "github",
            _http_get=fake_get, _http_post=fake_post,
        )
        verifier.verify("t", "o", "r", 1)
        assert fake_post.calls[0]["headers"]["Accept"] == "application/vnd.github.v3+json"

    def test_forgejo_write_check_no_github_accept_header(self) -> None:
        fake_get = FakeHttpCaller(responses=[FakeResponse(200)])
        fake_post = FakeHttpCaller(responses=[FakeResponse(200)])
        verifier = PreflightVerifier(
            "https://api.example.com", "forgejo",
            _http_get=fake_get, _http_post=fake_post,
        )
        verifier.verify("t", "o", "r", 1)
        assert "Accept" not in fake_post.calls[0]["headers"]
