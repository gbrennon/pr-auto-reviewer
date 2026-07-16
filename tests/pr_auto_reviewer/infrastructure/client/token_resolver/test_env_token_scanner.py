"""Tests for EnvTokenScanner."""

from pr_auto_reviewer.infrastructure.client.token_resolver.env_token_scanner import (
    EnvTokenScanner,
)


def _scanner(prefix: str, **env: str) -> EnvTokenScanner:
    return EnvTokenScanner(prefix, environ=env)


class TestEnvTokenScanner:
    def test_returns_empty_when_no_matching_env_vars(self):
        scanner = _scanner("GITHUB_TOKEN_")
        assert scanner.tokens_by_org() == {}

    def test_single_org_single_role(self):
        scanner = _scanner(
            "GITHUB_TOKEN_",
            GITHUB_TOKEN_myorg_OWNER="tok-123",
        )
        tokens = scanner.tokens_by_org()

        assert "myorg" in tokens
        assert "OWNER" in tokens["myorg"]
        token_value, source_key = tokens["myorg"]["OWNER"]
        assert token_value == "tok-123"
        assert source_key == "GITHUB_TOKEN_myorg_OWNER"

    def test_multiple_roles_for_same_org(self):
        scanner = _scanner(
            "GITHUB_TOKEN_",
            GITHUB_TOKEN_myorg_OWNER="owner-tok",
            GITHUB_TOKEN_myorg_REVIEWER="reviewer-tok",
        )
        tokens = scanner.tokens_by_org()

        assert tokens["myorg"]["OWNER"][0] == "owner-tok"
        assert tokens["myorg"]["REVIEWER"][0] == "reviewer-tok"

    def test_multiple_orgs(self):
        scanner = _scanner(
            "GITHUB_TOKEN_",
            GITHUB_TOKEN_org1_OWNER="tok1",
            GITHUB_TOKEN_org2_OWNER="tok2",
        )
        tokens = scanner.tokens_by_org()

        assert tokens["org1"]["OWNER"][0] == "tok1"
        assert tokens["org2"]["OWNER"][0] == "tok2"

    def test_ignores_non_matching_prefix(self):
        scanner = _scanner(
            "GITHUB_TOKEN_",
            FORGEJO_TOKEN_myorg_OWNER="fj-tok",
            GITHUB_TOKEN_myorg_OWNER="gh-tok",
        )
        tokens = scanner.tokens_by_org()

        assert "myorg" in tokens
        assert tokens["myorg"]["OWNER"][0] == "gh-tok"

    def test_ignores_unknown_role_suffix(self):
        scanner = _scanner(
            "GITHUB_TOKEN_",
            GITHUB_TOKEN_myorg_BOGUS="bogus-tok",
        )
        tokens = scanner.tokens_by_org()

        assert "myorg" not in tokens

    def test_stores_env_var_key_as_source(self):
        scanner = _scanner(
            "FORGEJO_TOKEN_",
            FORGEJO_TOKEN_a_OWNER="fj-own",
        )
        tokens = scanner.tokens_by_org()

        assert tokens["a"]["OWNER"][1] == "FORGEJO_TOKEN_a_OWNER"
