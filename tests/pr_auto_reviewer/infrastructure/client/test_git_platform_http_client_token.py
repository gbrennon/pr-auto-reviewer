"""Tests for GitPlatformHttpClient token resolution and preflight verification."""

from __future__ import annotations

import os
import json
from typing import Any

import pytest

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

    def test_verify_token_for_pr_no_resolver_does_nothing(self, tmp_path) -> None:
        """When no token_resolver is configured the call is a no-op, even
        when a preflight_verifier is present."""
        verifier = FakeVerifier()
        client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            preflight_verifier=verifier,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=tmp_path / "verified-tokens.json",
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        client.verify_token_for_pr(pr_id)
        assert len(verifier.calls) == 0

    # ------------------------------------------------------------------
    # verify_token_for_pr — caching and default skip
    # ------------------------------------------------------------------
    def test_verify_token_for_pr_same_org_cached(self, tmp_path) -> None:
        """The first verify_token_for_pr call verifies; a second call for
        the same (org, role) pair is a cache hit and skips verification."""
        verifier = FakeVerifier()
        resolver = FakeTokenResolver({"my-org/repo": "org-token"})
        client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            token_resolver=resolver,
            preflight_verifier=verifier,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=tmp_path / "verified-tokens.json",
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        client.verify_token_for_pr(pr_id)
        assert len(verifier.calls) == 1
        assert verifier.calls[0]["org"] == "my-org"
        assert verifier.calls[0]["role"] == "reviewer"

        # Second call -- same org, same role -- must be a cache hit.
        client.verify_token_for_pr(pr_id)
        assert len(verifier.calls) == 1

    def test_verify_token_for_pr_verifies_default_token(self, tmp_path) -> None:
        verifier = FakeVerifier()
        resolver = FakeTokenResolver({"my-org/repo": "default-token"})
        client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            token_resolver=resolver,
            preflight_verifier=verifier,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=tmp_path / "verified-tokens.json",
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        client.verify_token_for_pr(pr_id)
        assert len(verifier.calls) == 1
        assert verifier.calls[0]["token"] == "default-token"

    # ------------------------------------------------------------------
    # verify_token_for_pr -- disk cache persistence
    # ------------------------------------------------------------------

    def test_verify_token_for_pr_loads_persisted_cache(
        self, tmp_path,
    ) -> None:
        """A client loads persisted (org, role) pairs on init and skips
        verification for already-cached pairs (restart simulation)."""
        cache_path = tmp_path / "verified-tokens.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps([["my-org", "reviewer"]]))

        verifier = FakeVerifier()
        resolver = FakeTokenResolver({"my-org/repo": "org-token"})
        client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            token_resolver=resolver,
            preflight_verifier=verifier,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=cache_path,
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        client.verify_token_for_pr(pr_id)

        assert len(verifier.calls) == 0

    def test_verify_token_for_pr_persists_after_first_verify(
        self, tmp_path,
    ) -> None:
        """After the first verify_token_for_pr call, the cache file contains
        the verified (org, role) pair."""
        cache_path = tmp_path / "verified-tokens.json"

        verifier = FakeVerifier()
        resolver = FakeTokenResolver({"my-org/repo": "org-token"})
        client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            token_resolver=resolver,
            preflight_verifier=verifier,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=cache_path,
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        client.verify_token_for_pr(pr_id)

        assert len(verifier.calls) == 1
        data = json.loads(cache_path.read_text())
        assert ["my-org", "reviewer"] in data

    def test_verify_token_for_pr_cache_hit_after_save_and_restart(
        self, tmp_path,
    ) -> None:
        """Preflight runs on first client, persists, then second client
        (restart simulation) loads from disk and skips verification."""
        cache_path = tmp_path / "verified-tokens.json"

        verifier1 = FakeVerifier()
        resolver1 = FakeTokenResolver({"my-org/repo": "org-token"})
        client1 = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            token_resolver=resolver1,
            preflight_verifier=verifier1,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=cache_path,
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        client1.verify_token_for_pr(pr_id)
        assert len(verifier1.calls) == 1

        # Simulate restart: new client, same cache path.
        verifier2 = FakeVerifier()
        resolver2 = FakeTokenResolver({"my-org/repo": "org-token"})
        client2 = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            token_resolver=resolver2,
            preflight_verifier=verifier2,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=cache_path,
        )
        client2.verify_token_for_pr(pr_id)
        assert len(verifier2.calls) == 0

    def test_verify_token_for_pr_merge_across_clients(
        self, tmp_path,
    ) -> None:
        """Owner and reviewer clients sharing the same cache file both
        persist their entries without overwriting each other."""
        cache_path = tmp_path / "verified-tokens.json"

        # First: owner client verifies.
        owner_verifier = FakeVerifier()
        owner_resolver = FakeTokenResolver({"my-org/repo": "owner-token"})
        owner_client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-owner",
            client_label="owner",
            token_resolver=owner_resolver,
            preflight_verifier=owner_verifier,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=cache_path,
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        owner_client.verify_token_for_pr(pr_id)
        assert len(owner_verifier.calls) == 1
        assert owner_verifier.calls[0]["role"] == "owner"

        # Second: reviewer client verifies (same org).
        reviewer_verifier = FakeVerifier()
        reviewer_resolver = FakeTokenResolver({"my-org/repo": "reviewer-token"})
        reviewer_client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-reviewer",
            client_label="reviewer",
            token_resolver=reviewer_resolver,
            preflight_verifier=reviewer_verifier,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=cache_path,
        )
        reviewer_client.verify_token_for_pr(pr_id)
        assert len(reviewer_verifier.calls) == 1
        assert reviewer_verifier.calls[0]["role"] == "reviewer"

        # Both entries persisted (no overwrite).
        data = json.loads(cache_path.read_text())
        assert ["my-org", "owner"] in data
        assert ["my-org", "reviewer"] in data

    def test_verify_token_for_pr_loads_corrupt_cache(
        self, tmp_path,
    ) -> None:
        """A corrupt cache file is treated as empty — the client loads
        an empty set and can still verify and persist normally."""
        cache_path = tmp_path / "verified-tokens.json"
        cache_path.write_text("this is not valid json {{{")

        verifier = FakeVerifier()
        resolver = FakeTokenResolver({"my-org/repo": "org-token"})
        client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            token_resolver=resolver,
            preflight_verifier=verifier,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=cache_path,
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        client.verify_token_for_pr(pr_id)

        # Corrupt cache should NOT prevent verification.
        assert len(verifier.calls) == 1
        # The save should overwrite the corrupt file with valid JSON.
        data = json.loads(cache_path.read_text())
        assert ["my-org", "reviewer"] in data

    def test_verify_token_for_pr_creates_parent_dirs_on_save(
        self, tmp_path,
    ) -> None:
        """When the cache path's parent directories don't exist, the save
        creates them so the file is written successfully."""
        cache_path = tmp_path / "deeply" / "nested" / "verified-tokens.json"

        verifier = FakeVerifier()
        resolver = FakeTokenResolver({"my-org/repo": "org-token"})
        client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            token_resolver=resolver,
            preflight_verifier=verifier,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=cache_path,
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)
        client.verify_token_for_pr(pr_id)

        assert cache_path.exists()
        data = json.loads(cache_path.read_text())
        assert ["my-org", "reviewer"] in data


    def test_verify_token_for_pr_persists_even_on_verification_failure(
        self, tmp_path,
    ) -> None:
        """The (org, role) pair is written to disk *before* preflight (TOCTOU
        fix).  When preflight raises ``PreflightVerificationError`` the entry
        is still persisted so a subsequent restart skips re-verification."""
        cache_path = tmp_path / "verified-tokens.json"

        failing_verifier = FakeVerifier(should_fail=True)
        resolver = FakeTokenResolver({"my-org/repo": "org-token"})
        client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            token_resolver=resolver,
            preflight_verifier=failing_verifier,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=cache_path,
        )
        pr_id = PullRequestId(repository="my-org/repo", number=1)

        with pytest.raises(PreflightVerificationError):
            client.verify_token_for_pr(pr_id)

        # Cache persisted despite the verification failure.
        assert cache_path.exists()
        data = json.loads(cache_path.read_text())
        assert ["my-org", "reviewer"] in data

        # A new client (restart simulation) skips verification.
        verifier2 = FakeVerifier()
        resolver2 = FakeTokenResolver({"my-org/repo": "org-token"})
        client2 = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            token_resolver=resolver2,
            preflight_verifier=verifier2,  # pyright: ignore[reportArgumentType]
            _verified_cache_path=cache_path,
        )
        client2.verify_token_for_pr(pr_id)
        assert len(verifier2.calls) == 0
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
