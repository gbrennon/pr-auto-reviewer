"""TokenVerifier tests — preflight skip when already cached."""

from __future__ import annotations

from pathlib import Path

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.token_verifier import TokenVerifier
from tests.fakes import FakeTokenResolver, FakeVerifier


class TestTokenVerifierSkipsWhenCached:
    @staticmethod
    def _client(
        label: str = "owner",
        verified_cache_path: Path | None = None,
    ) -> GitPlatformHttpClient:
        resolver = FakeTokenResolver({"o/r": f"{label}-tok"})
        verifier = FakeVerifier()
        return GitPlatformHttpClient(
            "https://api.example.com",
            f"default-{label}",
            platform_mode="forgejo",
            client_label=label,
            token_resolver=resolver,
            preflight_verifier=verifier,
            _verified_cache_path=verified_cache_path,
        )

    def test_verify_skips_on_second_call_within_same_instance(
        self, tmp_path: Path
    ) -> None:
        cache = tmp_path / "verified-tokens.json"
        owner = TestTokenVerifierSkipsWhenCached._client(
            "owner", verified_cache_path=cache,
        )
        reviewer = TestTokenVerifierSkipsWhenCached._client(
            "reviewer", verified_cache_path=cache,
        )
        verifier = TokenVerifier(owner, reviewer, persist=False)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)
        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 1
        assert len(reviewer._preflight_verifier.calls) == 1

    def test_verify_skips_when_no_org_in_repository(
        self, tmp_path: Path
    ) -> None:
        cache = tmp_path / "verified-tokens.json"
        owner = TestTokenVerifierSkipsWhenCached._client(
            "owner", verified_cache_path=cache,
        )
        reviewer = TestTokenVerifierSkipsWhenCached._client(
            "reviewer", verified_cache_path=cache,
        )
        verifier = TokenVerifier(owner, reviewer, persist=False)
        pr_id = PullRequestId(repository="norepo", number=1)

        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 0

    def test_verify_skips_when_repository_starts_with_slash(
        self, tmp_path: Path
    ) -> None:
        cache = tmp_path / "verified-tokens.json"
        owner = TestTokenVerifierSkipsWhenCached._client(
            "owner", verified_cache_path=cache,
        )
        reviewer = TestTokenVerifierSkipsWhenCached._client(
            "reviewer", verified_cache_path=cache,
        )
        verifier = TokenVerifier(owner, reviewer, persist=False)
        pr_id = PullRequestId(repository="/repo", number=1)

        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 0
