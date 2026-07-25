"""TokenVerifier tests — preflight delegation and caching."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.token_verifier import TokenVerifier
from tests.fakes.token_fakes import FakeTokenResolver, FakeVerifier
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)


def _client(
    label: str = "owner",
    verified_cache_path: Path | None = None,
) -> GitPlatformHttpClient:
    resolver = FakeTokenResolver({f"o/r": f"{label}-tok"})
    verifier = FakeVerifier()
    return GitPlatformHttpClient(
        "https://api.example.com",
        f"default-{label}",
        platform_mode="forgejo",
        client_label=label,
        token_resolver=resolver,
        preflight_verifier=verifier,  # pyright: ignore[reportArgumentType]
        _verified_cache_path=verified_cache_path,
    )


class TestTokenVerifierDelegatesToClients:
    def test_verify_calls_owner_client_preflight(self, tmp_path: Path) -> None:
        cache = tmp_path / "verified-tokens.json"
        owner = _client("owner", verified_cache_path=cache)
        reviewer = _client("reviewer", verified_cache_path=cache)
        verifier = TokenVerifier(owner, reviewer, persist=False)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)

        owner_preflight = owner._preflight_verifier
        assert len(owner_preflight.calls) == 1
        assert owner_preflight.calls[0]["role"] == "owner"

    def test_verify_calls_reviewer_client_preflight(self, tmp_path: Path) -> None:
        cache = tmp_path / "verified-tokens.json"
        owner = _client("owner", verified_cache_path=cache)
        reviewer = _client("reviewer", verified_cache_path=cache)
        verifier = TokenVerifier(owner, reviewer, persist=False)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)

        reviewer_preflight = reviewer._preflight_verifier
        assert len(reviewer_preflight.calls) == 1
        assert reviewer_preflight.calls[0]["role"] == "reviewer"


class TestTokenVerifierSkipsWhenCached:
    def test_verify_skips_on_second_call_within_same_instance(
        self, tmp_path: Path
    ) -> None:
        cache = tmp_path / "verified-tokens.json"
        owner = _client("owner", verified_cache_path=cache)
        reviewer = _client("reviewer", verified_cache_path=cache)
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
        owner = _client("owner", verified_cache_path=cache)
        reviewer = _client("reviewer", verified_cache_path=cache)
        verifier = TokenVerifier(owner, reviewer, persist=False)
        pr_id = PullRequestId(repository="norepo", number=1)

        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 0

    def test_verify_skips_when_repository_starts_with_slash(
        self, tmp_path: Path
    ) -> None:
        cache = tmp_path / "verified-tokens.json"
        owner = _client("owner", verified_cache_path=cache)
        reviewer = _client("reviewer", verified_cache_path=cache)
        verifier = TokenVerifier(owner, reviewer, persist=False)
        pr_id = PullRequestId(repository="/repo", number=1)

        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 0


class TestTokenVerifierPersistence:
    def test_verify_persists_verified_pairs_when_persist_is_true(
        self, tmp_path: Path
    ) -> None:
        store = tmp_path / "verified-tokens.json"
        owner = _client("owner", verified_cache_path=store)
        reviewer = _client("reviewer", verified_cache_path=store)
        verifier = TokenVerifier(owner, reviewer, persist=True, _store_path=store)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)

        assert store.exists()
        data = json.loads(store.read_text())
        assert ["o", "owner"] in data
        assert ["o", "reviewer"] in data

    def test_verify_loads_persisted_pairs_and_skips_preflight(
        self, tmp_path: Path
    ) -> None:
        store = tmp_path / "verified-tokens.json"
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(json.dumps([["o", "owner"], ["o", "reviewer"]]))

        owner = _client("owner", verified_cache_path=store)
        reviewer = _client("reviewer", verified_cache_path=store)
        verifier = TokenVerifier(owner, reviewer, persist=True, _store_path=store)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 0
        assert len(reviewer._preflight_verifier.calls) == 0

    def test_verify_does_not_persist_when_persist_is_false(
        self, tmp_path: Path
    ) -> None:
        store = tmp_path / "verified-tokens.json"
        owner = _client("owner", verified_cache_path=store)
        reviewer = _client("reviewer", verified_cache_path=store)
        verifier = TokenVerifier(owner, reviewer, persist=False, _store_path=store)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)

        assert store.exists()
        data = json.loads(store.read_text())
        assert ["o", "owner"] in data
        assert ["o", "reviewer"] in data

    def test_load_handles_corrupt_json(self, tmp_path: Path) -> None:
        store = tmp_path / "verified-tokens.json"
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text("not json")

        owner = _client("owner", verified_cache_path=store)
        reviewer = _client("reviewer", verified_cache_path=store)
        verifier = TokenVerifier(owner, reviewer, persist=True, _store_path=store)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 1
