"""Tests for TokenRoleDefaults."""

from pr_auto_reviewer.infrastructure.client.token_defaults import TokenDefaults
from pr_auto_reviewer.infrastructure.client.token_resolver.token_role_defaults import (
    TokenRoleDefaults,
)


class TestTokenRoleDefaults:
    def test_owner_role_returns_owner_token(self):
        defaults = TokenDefaults(owner_token="own-tok")
        role_defaults = TokenRoleDefaults("GITHUB", defaults)
        assert role_defaults.token_for("OWNER") == "own-tok"

    def test_reviewer_role_returns_reviewer_token(self):
        defaults = TokenDefaults(reviewer_token="rev-tok")
        role_defaults = TokenRoleDefaults("GITHUB", defaults)
        assert role_defaults.token_for("REVIEWER") == "rev-tok"

    def test_unknown_role_returns_empty(self):
        defaults = TokenDefaults(owner_token="own-tok")
        role_defaults = TokenRoleDefaults("GITHUB", defaults)
        assert role_defaults.token_for("BOGUS") == ""

    def test_source_key_for_owner(self):
        defaults = TokenDefaults()
        role_defaults = TokenRoleDefaults("GITHUB", defaults)
        assert role_defaults.source_key_for("OWNER") == "GITHUB_OWNER_TOKEN"

    def test_source_key_for_reviewer(self):
        defaults = TokenDefaults()
        role_defaults = TokenRoleDefaults("FORGEJO", defaults)
        assert role_defaults.source_key_for("REVIEWER") == "FORGEJO_REVIEWER_TOKEN"

    def test_source_key_normalizes_role_case(self):
        defaults = TokenDefaults()
        role_defaults = TokenRoleDefaults("GITHUB", defaults)
        assert role_defaults.source_key_for("owner") == "GITHUB_OWNER_TOKEN"

    def test_reviewer_username_returns_default(self):
        defaults = TokenDefaults(reviewer_username="rev-user")
        role_defaults = TokenRoleDefaults("GITHUB", defaults)
        assert role_defaults.reviewer_username() == "rev-user"
