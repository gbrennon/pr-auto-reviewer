from ._helpers import *
from .test_token_verifier_delegates_to_clients import (
    TestTokenVerifierDelegatesToClients,
)


class TestTokenVerifierPersistence:
    def test_verify_persists_verified_pairs_when_persist_is_true(
        self, tmp_path: Path
    ) -> None:
        store = tmp_path / "verified-tokens.json"
        owner = TestTokenVerifierDelegatesToClients._client("owner", verified_cache_path=store)
        reviewer = TestTokenVerifierDelegatesToClients._client("reviewer", verified_cache_path=store)
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

        owner = TestTokenVerifierDelegatesToClients._client("owner", verified_cache_path=store)
        reviewer = TestTokenVerifierDelegatesToClients._client("reviewer", verified_cache_path=store)
        verifier = TokenVerifier(owner, reviewer, persist=True, _store_path=store)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 0
        assert len(reviewer._preflight_verifier.calls) == 0

    def test_verify_does_not_persist_when_persist_is_false(
        self, tmp_path: Path
    ) -> None:
        store = tmp_path / "verified-tokens.json"
        owner = TestTokenVerifierDelegatesToClients._client("owner", verified_cache_path=store)
        reviewer = TestTokenVerifierDelegatesToClients._client("reviewer", verified_cache_path=store)
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

        owner = TestTokenVerifierDelegatesToClients._client("owner", verified_cache_path=store)
        reviewer = TestTokenVerifierDelegatesToClients._client("reviewer", verified_cache_path=store)
        verifier = TokenVerifier(owner, reviewer, persist=True, _store_path=store)
        pr_id = PullRequestId(repository="o/r", number=1)

        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 1

    def test_default_store_path_when_not_provided_then_uses_app_paths_cache_dir(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """Verify default store path resolves to AppPaths.cache_dir() / 'verified-tokens.json'."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        owner = TestTokenVerifierDelegatesToClients._client("owner")
        reviewer = TestTokenVerifierDelegatesToClients._client("reviewer")

        verifier = TokenVerifier(owner, reviewer, persist=False)

        assert verifier._store_path == tmp_path / "pr-auto-reviewer" / "verified-tokens.json"

