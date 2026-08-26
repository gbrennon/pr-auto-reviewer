from ._helpers import *
from .test_token_verifier_delegates_to_clients import (
    TestTokenVerifierDelegatesToClients,
)


class TestTokenVerifierSkipsWhenCached:
    def test_verify_skips_on_second_call_within_same_instance(
        self, tmp_path: Path
    ) -> None:
        cache = tmp_path / "verified-tokens.json"
        owner = TestTokenVerifierDelegatesToClients._client("owner", verified_cache_path=cache)
        reviewer = TestTokenVerifierDelegatesToClients._client("reviewer", verified_cache_path=cache)
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
        owner = TestTokenVerifierDelegatesToClients._client("owner", verified_cache_path=cache)
        reviewer = TestTokenVerifierDelegatesToClients._client("reviewer", verified_cache_path=cache)
        verifier = TokenVerifier(owner, reviewer, persist=False)
        pr_id = PullRequestId(repository="norepo", number=1)

        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 0

    def test_verify_skips_when_repository_starts_with_slash(
        self, tmp_path: Path
    ) -> None:
        cache = tmp_path / "verified-tokens.json"
        owner = TestTokenVerifierDelegatesToClients._client("owner", verified_cache_path=cache)
        reviewer = TestTokenVerifierDelegatesToClients._client("reviewer", verified_cache_path=cache)
        verifier = TokenVerifier(owner, reviewer, persist=False)
        pr_id = PullRequestId(repository="/repo", number=1)

        verifier.verify(pr_id)

        assert len(owner._preflight_verifier.calls) == 0

