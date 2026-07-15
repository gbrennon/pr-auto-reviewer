"""Unit tests for TokenResolver."""

import pytest
from pr_auto_reviewer.infrastructure.client.token_resolver import (
    TokenDefaults,
    TokenResolver,
)


@pytest.fixture
def defaults() -> TokenDefaults:
    """Default tokens used as fallbacks in every test."""
    return TokenDefaults(
        owner_token="default-owner",
        reviewer_token="default-reviewer",
        reviewer_username="default-username",
    )


class TestTokenResolverBasics:
    """Tests for the basic resolution paths — no overrides, fallbacks."""
    def test_no_overrides_returns_defaults(self, monkeypatch, defaults):
        """All roles return defaults when no org env vars are set."""
        monkeypatch.delenv("GITHUB_TOKEN_myorg_OWNER", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN_myorg_REVIEWER", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN_myorg_REVIEWER_USERNAME", raising=False)

        resolver = TokenResolver("GITHUB", defaults)

        assert resolver.resolve("OWNER", "myorg/repo") == "default-owner"
        assert resolver.resolve("REVIEWER", "myorg/repo") == "default-reviewer"
        # _default_for returns "" for REVIEWER_USERNAME; use reviewer_username() for defaults
        assert resolver.resolve("REVIEWER_USERNAME", "myorg/repo") == ""
        assert resolver.reviewer_username("myorg/repo") == "default-username"

    def test_empty_repo_falls_back_to_default(self, monkeypatch, defaults):
        """Empty repo string → _extract_org returns '' → fallback to defaults."""
        monkeypatch.setenv("GITHUB_TOKEN_myorg_OWNER", "org-owner-token")

        resolver = TokenResolver("GITHUB", defaults)

        assert resolver.resolve("OWNER", "") == "default-owner"
        assert resolver.resolve("REVIEWER", "") == "default-reviewer"
        assert resolver.reviewer_username("") == "default-username"

    def test_repo_without_slash_falls_back_to_default(self, monkeypatch, defaults):
        """Repo without '/' → _extract_org returns '' → fallback to defaults."""
        monkeypatch.setenv("GITHUB_TOKEN_myrepo_OWNER", "org-owner-token")

        resolver = TokenResolver("GITHUB", defaults)

        assert resolver.resolve("OWNER", "myrepo") == "default-owner"
        assert resolver.resolve("REVIEWER", "myrepo") == "default-reviewer"
        assert resolver.reviewer_username("myrepo") == "default-username"

    def test_unknown_role_falls_back_to_default(self, monkeypatch, defaults):
        """Calling resolve() with an unknown role returns ''."""
        monkeypatch.setenv("GITHUB_TOKEN_myorg_OWNER", "org-owner-token")

        resolver = TokenResolver("GITHUB", defaults)

        assert resolver.resolve("BOGUS", "myorg/repo") == ""


class TestTokenResolverOrgOverrides:
    """Tests for per-org token overrides."""

    def test_org_override_owner(self, monkeypatch, defaults):
        """GITHUB_TOKEN_myorg_OWNER overrides the owner token for that org."""
        monkeypatch.setenv("GITHUB_TOKEN_myorg_OWNER", "org-owner-token")

        resolver = TokenResolver("GITHUB", defaults)

        assert resolver.resolve("OWNER", "myorg/repo") == "org-owner-token"
        # Other roles still fall back
        assert resolver.resolve("REVIEWER", "myorg/repo") == "default-reviewer"
        assert resolver.reviewer_username("myorg/repo") == "default-username"

    def test_org_override_reviewer(self, monkeypatch, defaults):
        """GITHUB_TOKEN_myorg_REVIEWER overrides the reviewer token."""
        monkeypatch.setenv("GITHUB_TOKEN_myorg_REVIEWER", "org-reviewer-token")

        resolver = TokenResolver("GITHUB", defaults)

        assert resolver.resolve("REVIEWER", "myorg/repo") == "org-reviewer-token"
        assert resolver.resolve("OWNER", "myorg/repo") == "default-owner"
        assert resolver.reviewer_username("myorg/repo") == "default-username"

    def test_org_override_reviewer_username(self, monkeypatch, defaults):
        """GITHUB_TOKEN_myorg_REVIEWER_USERNAME overrides the username."""
        monkeypatch.setenv(
            "GITHUB_TOKEN_myorg_REVIEWER_USERNAME", "org-reviewer-username"
        )

        resolver = TokenResolver("GITHUB", defaults)

        assert resolver.resolve(
            "REVIEWER_USERNAME", "myorg/repo"
        ) == "org-reviewer-username"
        assert resolver.reviewer_username("myorg/repo") == "org-reviewer-username"
        assert resolver.resolve("OWNER", "myorg/repo") == "default-owner"
        assert resolver.resolve("REVIEWER", "myorg/repo") == "default-reviewer"

    def test_mixed_override_reviewer_only(self, monkeypatch, defaults):
        """Only REVIEWER is overridden; OWNER falls back to default."""
        monkeypatch.setenv("GITHUB_TOKEN_myorg_REVIEWER", "org-reviewer-token")

        resolver = TokenResolver("GITHUB", defaults)

        assert resolver.resolve("REVIEWER", "myorg/repo") == "org-reviewer-token"
        assert resolver.resolve("OWNER", "myorg/repo") == "default-owner"

    def test_org_name_with_underscores(self, monkeypatch, defaults):
        """Org name containing underscores is parsed correctly."""
        monkeypatch.setenv(
            "GITHUB_TOKEN_my_org_OWNER", "underscore-org-owner-token"
        )

        resolver = TokenResolver("GITHUB", defaults)

        assert (
            resolver.resolve("OWNER", "my_org/repo")
            == "underscore-org-owner-token"
        )
        # A different org is unaffected
        assert resolver.resolve("OWNER", "myorg/repo") == "default-owner"

    def test_unknown_role_suffix_ignored(self, monkeypatch, defaults):
        """GITHUB_TOKEN_myorg_BOGUS does not create an override entry
        and does not interfere with known roles."""
        monkeypatch.setenv("GITHUB_TOKEN_myorg_BOGUS", "bogus-token")
        monkeypatch.setenv("GITHUB_TOKEN_myorg_OWNER", "org-owner-token")

        resolver = TokenResolver("GITHUB", defaults)

        # BOGUS is not a known role — resolve returns default
        assert resolver.resolve("BOGUS", "myorg/repo") == ""
        # OWNER still resolves correctly
        assert resolver.resolve("OWNER", "myorg/repo") == "org-owner-token"


class TestTokenResolverMultipleOrgs:
    """Tests for multiple-org scenarios."""

    def test_multiple_orgs_different_overrides(self, monkeypatch, defaults):
        """Two different orgs with different override sets resolve independently."""
        monkeypatch.setenv("GITHUB_TOKEN_org1_OWNER", "org1-owner")
        monkeypatch.setenv("GITHUB_TOKEN_org2_REVIEWER", "org2-reviewer")

        resolver = TokenResolver("GITHUB", defaults)

        # org1: OWNER overridden, REVIEWER falls back
        assert resolver.resolve("OWNER", "org1/repo") == "org1-owner"
        assert resolver.resolve("REVIEWER", "org1/repo") == "default-reviewer"

        # org2: REVIEWER overridden, OWNER falls back
        assert resolver.resolve("REVIEWER", "org2/repo") == "org2-reviewer"
        assert resolver.resolve("OWNER", "org2/repo") == "default-owner"

        # Unknown org falls back entirely
        assert resolver.resolve("OWNER", "org3/repo") == "default-owner"

    def test_overlapping_org_names(self, monkeypatch, defaults):
        """Org 'my' and 'my_org' are distinct and do not interfere."""
        monkeypatch.setenv("GITHUB_TOKEN_my_OWNER", "short-org-owner")
        monkeypatch.setenv("GITHUB_TOKEN_my_org_OWNER", "long-org-owner")

        resolver = TokenResolver("GITHUB", defaults)

        assert resolver.resolve("OWNER", "my/repo") == "short-org-owner"
        assert resolver.resolve("OWNER", "my_org/repo") == "long-org-owner"


class TestTokenResolverForgejoPrefix:
    """Tests for the FORGEJO platform prefix."""

    def test_forgejo_prefix_resolves_owner(self, monkeypatch, defaults):
        """FORGEJO_TOKEN_... env vars are scanned and resolved."""
        monkeypatch.setenv("FORGEJO_TOKEN_myorg_OWNER", "forgejo-owner-token")

        resolver = TokenResolver("FORGEJO", defaults)

        assert resolver.resolve("OWNER", "myorg/repo") == "forgejo-owner-token"

    def test_forgejo_prefix_does_not_conflict_with_github(self, monkeypatch, defaults):
        """GITHUB_TOKEN_* and FORGEJO_TOKEN_* are independent."""
        monkeypatch.setenv("GITHUB_TOKEN_myorg_OWNER", "github-owner")
        monkeypatch.setenv("FORGEJO_TOKEN_myorg_OWNER", "forgejo-owner")

        github_resolver = TokenResolver("GITHUB", defaults)
        forgejo_resolver = TokenResolver("FORGEJO", defaults)

        assert github_resolver.resolve("OWNER", "myorg/repo") == "github-owner"
        assert forgejo_resolver.resolve("OWNER", "myorg/repo") == "forgejo-owner"

    def test_forgejo_prefix_reviewer_and_username(self, monkeypatch, defaults):
        """Full FORGEJO override suite — OWNER, REVIEWER, REVIEWER_USERNAME."""
        monkeypatch.setenv("FORGEJO_TOKEN_myorg_OWNER", "fj-owner")
        monkeypatch.setenv("FORGEJO_TOKEN_myorg_REVIEWER", "fj-reviewer")
        monkeypatch.setenv(
            "FORGEJO_TOKEN_myorg_REVIEWER_USERNAME", "fj-username"
        )

        resolver = TokenResolver("FORGEJO", defaults)

        assert resolver.resolve("OWNER", "myorg/repo") == "fj-owner"
        assert resolver.resolve("REVIEWER", "myorg/repo") == "fj-reviewer"
        assert (
            resolver.resolve("REVIEWER_USERNAME", "myorg/repo")
            == "fj-username"
        )
        assert resolver.reviewer_username("myorg/repo") == "fj-username"


class TestTokenResolverCaseInsensitivity:
    """Prefix and role matching is case-insensitive."""

    def test_lowercase_platform_prefix(self, monkeypatch, defaults):
        """TokenResolver('github', ...) works identically to 'GITHUB'."""
        monkeypatch.setenv("GITHUB_TOKEN_myorg_OWNER", "org-owner-token")

        resolver = TokenResolver("github", defaults)

        assert resolver.resolve("OWNER", "myorg/repo") == "org-owner-token"

    def test_lowercase_role_resolves_org_override(
        self, monkeypatch, defaults
    ):
        """resolve() normalises the role to uppercase before the org-entry
        lookup, so lowercase roles match the uppercase keys stored by
        _scan_env.
        """
        monkeypatch.setenv("GITHUB_TOKEN_myorg_OWNER", "org-owner-token")
        monkeypatch.setenv("GITHUB_TOKEN_myorg_REVIEWER", "org-reviewer-token")

        resolver = TokenResolver("GITHUB", defaults)

        assert resolver.resolve("owner", "myorg/repo") == "org-owner-token"
        assert resolver.resolve("reviewer", "myorg/repo") == "org-reviewer-token"
        assert resolver.resolve("OWNER", "myorg/repo") == "org-owner-token"
        assert resolver.resolve("REVIEWER", "myorg/repo") == "org-reviewer-token"


class TestTokenResolverDefaults:
    """Tests for the TokenDefaults dataclass."""

    def test_token_defaults_all_empty_by_default(self):
        """TokenDefaults defaults all tokens to empty strings."""
        d = TokenDefaults()
        assert d.owner_token == ""
        assert d.reviewer_token == ""
        assert d.reviewer_username == ""

    def test_token_defaults_is_frozen(self):
        """TokenDefaults is immutable (frozen=True)."""
        d = TokenDefaults(owner_token="t")
        with pytest.raises(Exception):
            d.owner_token = "new"  # type: ignore[misc]

    def test_token_defaults_custom_values(self):
        """TokenDefaults accepts custom values for all fields."""
        d = TokenDefaults(
            owner_token="abc",
            reviewer_token="def",
            reviewer_username="ghi",
        )
        assert d.owner_token == "abc"
        assert d.reviewer_token == "def"
        assert d.reviewer_username == "ghi"
