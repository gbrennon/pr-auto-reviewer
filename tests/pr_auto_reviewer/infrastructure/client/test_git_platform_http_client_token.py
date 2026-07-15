"""Tests for GitPlatformHttpClient token resolution and preflight verification."""

from __future__ import annotations

import os
from typing import Any

from pr_auto_reviewer.domain.exceptions.preflight_verification_error import (
    PreflightVerificationError,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.client.token_resolver import (
    TokenDefaults,
    TokenResolver,
)

from tests.fakes.token_fakes import FakeTokenResolver, FakeVerifier


class TestGitPlatformHttpClientTokens:
    """Tests for token resolution and preflight verification behaviour."""

    # ------------------------------------------------------------------
    # _resolve_token_for_repo
    # ------------------------------------------------------------------

    def test_resolve_token_for_repo_no_resolver_returns_default(self) -> None:
        """When no TokenResolver is configured, _resolve_token_for_repo
        always returns the default token regardless of repo."""
        client = GitPlatformHttpClient("https://api.example.com", "default-token")
        result = client._resolve_token_for_repo("my-org/repo")
        assert result == "default-token"

    def test_resolve_token_for_repo_none_repo_returns_default(self) -> None:
        """When repo is None, _resolve_token_for_repo returns the default
        token even when a resolver is configured."""
        resolver = FakeTokenResolver({"my-org/repo": "org-token"})
        client = GitPlatformHttpClient(
            "https://api.example.com", "default-token", token_resolver=resolver,
        )
        result = client._resolve_token_for_repo(None)
        assert result == "default-token"

    def test_resolve_token_for_repo_resolves_via_resolver(self) -> None:
        """_resolve_token_for_repo delegates to TokenResolver when one is
        configured and returns the resolved per-org token."""
        env_key = "GITHUB_TOKEN_my-org_OWNER"
        os.environ[env_key] = "org-token-123"
        try:
            resolver = TokenResolver("GITHUB", TokenDefaults(owner_token="default-owner"))
            client = GitPlatformHttpClient(
                "https://api.example.com",
                "default-owner",
                client_label="OWNER",
                token_resolver=resolver,
            )
            result = client._resolve_token_for_repo("my-org/repo")
            assert result == "org-token-123"
        finally:
            del os.environ[env_key]

    def test_resolve_token_for_repo_lowercase_client_label(self) -> None:
        """When the client_label is lowercase (e.g. "owner"), the TokenResolver
        still matches the uppercase org-entry key and returns the per-org
        override instead of falling back to the default."""
        env_key = "GITHUB_TOKEN_my-org_OWNER"
        os.environ[env_key] = "org-token-456"
        try:
            resolver = TokenResolver("GITHUB", TokenDefaults(owner_token="default-owner"))
            client = GitPlatformHttpClient(
                "https://api.example.com",
                "default-owner",
                client_label="owner",
                token_resolver=resolver,
            )
            result = client._resolve_token_for_repo("my-org/repo")
            assert result == "org-token-456"
        finally:
            del os.environ[env_key]

    def test_resolve_token_for_repo_resolver_returns_empty_falls_back(self) -> None:
        """When the resolver returns an empty string, _resolve_token_for_repo
        falls back to the default token."""
        resolver = FakeTokenResolver({"my-org/repo": ""})
        client = GitPlatformHttpClient(
            "https://api.example.com", "default-token", token_resolver=resolver,
        )
        result = client._resolve_token_for_repo("my-org/repo")
        assert result == "default-token"

    # ------------------------------------------------------------------
    # verify_token_for_pr — early exits
    # ------------------------------------------------------------------

    def test_verify_token_for_pr_no_verifier_does_nothing(self) -> None:
        """When no preflight_verifier is configured the call is a no-op."""
        client = GitPlatformHttpClient("https://api.example.com", "default-token")
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        client.verify_token_for_pr(pr_id)  # does not raise

    def test_verify_token_for_pr_no_resolver_does_nothing(self) -> None:
        """When no token_resolver is configured the call is a no-op, even
        when a preflight_verifier is present."""
        verifier = FakeVerifier()
        client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            preflight_verifier=verifier,  # pyright: ignore[reportArgumentType]
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        client.verify_token_for_pr(pr_id)
        assert len(verifier.calls) == 0

    # ------------------------------------------------------------------
    # verify_token_for_pr — caching and default skip
    # ------------------------------------------------------------------

    def test_verify_token_for_pr_same_org_cached(self) -> None:
        """The first verify_token_for_pr call verifies; a second call for
        the same (org, role) pair is a cache hit and skips verification."""
        verifier = FakeVerifier()
        resolver = FakeTokenResolver({"my-org/repo": "org-token"})
        client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            token_resolver=resolver,
            preflight_verifier=verifier,  # pyright: ignore[reportArgumentType]
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        client.verify_token_for_pr(pr_id)
        assert len(verifier.calls) == 1
        assert verifier.calls[0]["org"] == "my-org"
        assert verifier.calls[0]["role"] == "reviewer"

        # Second call — same org, same role — must be a cache hit.
        client.verify_token_for_pr(pr_id)
        assert len(verifier.calls) == 1

    def test_verify_token_for_pr_default_token_skips(self) -> None:
        """When the resolved token equals the client's default token,
        preflight verification is skipped entirely."""
        verifier = FakeVerifier()
        resolver = FakeTokenResolver({"my-org/repo": "default-token"})
        client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            token_resolver=resolver,
            preflight_verifier=verifier,  # pyright: ignore[reportArgumentType]
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        client.verify_token_for_pr(pr_id)
        assert len(verifier.calls) == 0

    # ------------------------------------------------------------------
    # _get_auth_header — repo propagation
    # ------------------------------------------------------------------

    def test_get_passes_repo_to_auth_header(self) -> None:
        """_get_auth_header passes the *repo* kwarg through to
        _resolve_token_for_repo, which in turn delegates to TokenResolver."""
        resolver = FakeTokenResolver({"my-org/repo": "org-token"})
        client = GitPlatformHttpClient(
            "https://api.example.com", "default-token", token_resolver=resolver,
        )
        header = client._get_auth_header(repo="my-org/repo")
        assert len(resolver.calls) == 1
        assert resolver.calls[0]["repo"] == "my-org/repo"
        assert header == {"Authorization": "token org-token"}
