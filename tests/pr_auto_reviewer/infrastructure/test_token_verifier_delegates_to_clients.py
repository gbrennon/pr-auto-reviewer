"""TokenVerifier tests — preflight delegation to owner and reviewer clients."""

from __future__ import annotations

from pathlib import Path

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.token_verifier import TokenVerifier
from tests.fakes import FakeTokenResolver, FakeVerifier


class TestTokenVerifierDelegatesToClients:
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

    def test_verify_calls_owner_client_preflight(self, tmp_path: Path) -> None:
        cache = tmp_path / "verified-tokens.json"
        owner = TestTokenVerifierDelegatesToClients._client(
            "owner", verified_cache_path=cache,
        )
        reviewer = TestTokenVerifierDelegatesToClients._client(
            "reviewer", verified_cache_path=cache,
        )
        verifier = TokenVerifier(owner, reviewer, persist=False)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)

        owner_preflight = owner._preflight_verifier
        assert len(owner_preflight.calls) == 1
        assert owner_preflight.calls[0]["role"] == "owner"

    def test_verify_calls_reviewer_client_preflight(self, tmp_path: Path) -> None:
        cache = tmp_path / "verified-tokens.json"
        owner = TestTokenVerifierDelegatesToClients._client(
            "owner", verified_cache_path=cache,
        )
        reviewer = TestTokenVerifierDelegatesToClients._client(
            "reviewer", verified_cache_path=cache,
        )
        verifier = TokenVerifier(owner, reviewer, persist=False)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)

        reviewer_preflight = reviewer._preflight_verifier
        assert len(reviewer_preflight.calls) == 1
        assert reviewer_preflight.calls[0]["role"] == "reviewer"
