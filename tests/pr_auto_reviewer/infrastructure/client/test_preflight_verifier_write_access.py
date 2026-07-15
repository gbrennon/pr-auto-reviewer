"""PreflightVerifier write-access check tests."""

from __future__ import annotations

import pytest
import requests

from tests.fakes.preflight_fakes import FakeHttpCaller, FakeResponse

from pr_auto_reviewer.domain.exceptions.preflight_verification_error import (
    PreflightVerificationError,
)
from pr_auto_reviewer.infrastructure.client.preflight_verifier import (
    PreflightVerifier,
)

class TestWriteAccessCheck:
    def test_200_passes(self) -> None:
        fake_get = FakeHttpCaller(responses=[FakeResponse(200)])
        fake_post = FakeHttpCaller(responses=[FakeResponse(200)])
        verifier = PreflightVerifier(
            "https://api.example.com", "forgejo",
            _http_get=fake_get, _http_post=fake_post,
        )
        verifier.verify("tok", "my-org", "my-repo", 42, "reviewer")
        assert "/repos/my-org/my-repo/pulls/42/requested_reviewers" in fake_post.calls[0]["url"]

    def test_422_passes(self) -> None:
        fake_get = FakeHttpCaller(responses=[FakeResponse(200)])
        fake_post = FakeHttpCaller(responses=[FakeResponse(422)])
        verifier = PreflightVerifier(
            "https://api.example.com", "forgejo",
            _http_get=fake_get, _http_post=fake_post,
        )
        verifier.verify("tok", "my-org", "my-repo", 1)

    def test_403_raises(self) -> None:
        fake_get = FakeHttpCaller(responses=[FakeResponse(200)])
        fake_post = FakeHttpCaller(responses=[FakeResponse(403)])
        verifier = PreflightVerifier(
            "https://api.example.com", "forgejo",
            _http_get=fake_get, _http_post=fake_post,
        )
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1)
        assert exc.value.http_status == 403
        assert exc.value.step == "write_access"

    def test_401_raises(self) -> None:
        fake_get = FakeHttpCaller(responses=[FakeResponse(200)])
        fake_post = FakeHttpCaller(responses=[FakeResponse(401)])
        verifier = PreflightVerifier(
            "https://api.example.com", "forgejo",
            _http_get=fake_get, _http_post=fake_post,
        )
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1)
        assert exc.value.http_status == 401
        assert exc.value.step == "write_access"

    def test_connection_error_raises(self) -> None:
        def raise_err(*args: Any, **kwargs: Any) -> None:
            raise requests.ConnectionError("timeout")

        fake_get = FakeHttpCaller(responses=[FakeResponse(200)])
        fake_post = raise_err
        verifier = PreflightVerifier(
            "https://api.example.com", "forgejo",
            _http_get=fake_get, _http_post=fake_post,
        )
        with pytest.raises(PreflightVerificationError) as exc:
            verifier.verify("tok", "my-org", "my-repo", 1)
        assert exc.value.http_status == 0
        assert exc.value.step == "write_access"
