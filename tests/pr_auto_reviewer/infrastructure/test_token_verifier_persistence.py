"""TokenVerifier tests — verified pair persistence."""

from __future__ import annotations

import json
from pathlib import Path

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.token_verifier import TokenVerifier
from tests.fakes import FakeTokenResolver, FakeVerifier


class TestTokenVerifierPersistence:
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

    def test_verify_persists_verified_pairs_when_persist_is_true(
        self, tmp_path: Path
    ) -> None:
        store = tmp_path / "verified-tokens.json"
        owner = TestTokenVerifierPersistence._client("owner", verified_cache_path=store)
        reviewer = TestTokenVerifierPersistence._client(
            "reviewer", verified_cache_path=store,
        )
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

        owner = TestTokenVerifierPersistence._client(
            "owner", verified_cache_path=store,
        )
        reviewer = TestTokenVerifierPersistence._client(
            "reviewer", verified_cache_path=store,
        )
        verifier = TokenVerifier(owner, reviewer, persist=True, _store_path=store)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 0
        assert len(reviewer._preflight_verifier.calls) == 0

    def test_verify_does_not_persist_when_persist_is_false(
        self, tmp_path: Path
    ) -> None:
        store = tmp_path / "verified-tokens.json"
        owner = TestTokenVerifierPersistence._client("owner", verified_cache_path=store)
        reviewer = TestTokenVerifierPersistence._client(
            "reviewer", verified_cache_path=store,
        )
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

        owner = TestTokenVerifierPersistence._client(
            "owner", verified_cache_path=store,
        )
        reviewer = TestTokenVerifierPersistence._client(
            "reviewer", verified_cache_path=store,
        )
        verifier = TokenVerifier(owner, reviewer, persist=True, _store_path=store)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 1
