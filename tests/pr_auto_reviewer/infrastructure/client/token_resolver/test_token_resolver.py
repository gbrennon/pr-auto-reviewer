"""Tests for TokenResolver composed behaviour."""

from pr_auto_reviewer.infrastructure.client.token_defaults import TokenDefaults
from pr_auto_reviewer.infrastructure.client.token_resolver import TokenResolver
from pr_auto_reviewer.infrastructure.client.token_resolver.env_token_scanner import (
    EnvTokenScanner,
)


def _resolver(
    platform_prefix: str = "GITHUB",
    owner_token: str = "default-owner",
    reviewer_token: str = "default-reviewer",
    reviewer_username: str = "default-username",
    **env: str,
) -> TokenResolver:
    defaults = TokenDefaults(
        owner_token=owner_token,
        reviewer_token=reviewer_token,
        reviewer_username=reviewer_username,
    )
    scanner = EnvTokenScanner(
        f"{platform_prefix.upper()}_TOKEN_", environ=env
    )
    return TokenResolver(platform_prefix, defaults, scanner=scanner)


class TestTokenResolverResolve:
    def test_resolve_returns_default_owner_token(self):
        resolver = _resolver()
        assert resolver.resolve("OWNER", "myorg/repo") == "default-owner"

    def test_resolve_returns_default_reviewer_token(self):
        resolver = _resolver()
        assert resolver.resolve("REVIEWER", "myorg/repo") == "default-reviewer"

    def test_resolve_returns_org_override_owner(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_OWNER="org-own")
        assert resolver.resolve("OWNER", "myorg/repo") == "org-own"

    def test_resolve_returns_org_override_reviewer(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_REVIEWER="org-rev")
        assert resolver.resolve("REVIEWER", "myorg/repo") == "org-rev"

    def test_resolve_returns_default_when_other_role_has_org_override(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_REVIEWER="org-rev")
        assert resolver.resolve("OWNER", "myorg/repo") == "default-owner"

    def test_resolve_falls_back_to_default_when_repo_is_empty(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_OWNER="org-own")
        assert resolver.resolve("OWNER", "") == "default-owner"

    def test_resolve_falls_back_to_default_when_repo_has_no_slash(self):
        resolver = _resolver(GITHUB_TOKEN_myrepo_OWNER="org-own")
        assert resolver.resolve("OWNER", "myrepo") == "default-owner"

    def test_resolve_returns_empty_for_unknown_role(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_OWNER="org-own")
        assert resolver.resolve("BOGUS", "myorg/repo") == ""

    def test_resolve_matches_lowercase_role_argument(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_OWNER="tok")
        assert resolver.resolve("owner", "myorg/repo") == "tok"

    def test_resolve_matches_lowercase_platform_prefix(self):
        resolver = _resolver(platform_prefix="github", GITHUB_TOKEN_myorg_OWNER="tok")
        assert resolver.resolve("OWNER", "myorg/repo") == "tok"

    def test_resolve_handles_org_name_with_underscores(self):
        resolver = _resolver(GITHUB_TOKEN_my_org_name_OWNER="tok")
        assert resolver.resolve("OWNER", "my_org_name/repo") == "tok"

    def test_resolve_returns_longest_suffix_match_for_overlapping_orgs(self):
        resolver = _resolver(
            GITHUB_TOKEN_foo_OWNER="foo-tok",
            GITHUB_TOKEN_foo_org_OWNER="foo-org-tok",
        )
        assert resolver.resolve("OWNER", "foo_org/repo") == "foo-org-tok"


class TestTokenResolverResolveSource:
    def test_resolve_source_returns_default_key_when_no_override(self):
        resolver = _resolver()
        _, source = resolver.resolve_source("OWNER", "myorg/repo")
        assert source == "GITHUB_OWNER_TOKEN"

    def test_resolve_source_returns_org_env_var_key(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_OWNER="org-tok")
        _, source = resolver.resolve_source("OWNER", "myorg/repo")
        assert source == "GITHUB_TOKEN_myorg_OWNER"


class TestTokenResolverReviewerUsername:
    def test_reviewer_username_returns_default(self):
        resolver = _resolver()
        assert resolver.reviewer_username("myorg/repo") == "default-username"

    def test_reviewer_username_returns_org_override(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_REVIEWER_USERNAME="org-user")
        assert resolver.reviewer_username("myorg/repo") == "org-user"


class TestTokenResolverForgejoPrefix:
    def test_resolve_returns_forgejo_org_override_owner(self):
        resolver = _resolver(
            platform_prefix="FORGEJO", FORGEJO_TOKEN_myorg_OWNER="fj-own"
        )
        assert resolver.resolve("OWNER", "myorg/repo") == "fj-own"

    def test_resolve_returns_forgejo_org_override_reviewer(self):
        resolver = _resolver(
            platform_prefix="FORGEJO", FORGEJO_TOKEN_myorg_REVIEWER="fj-rev"
        )
        assert resolver.resolve("REVIEWER", "myorg/repo") == "fj-rev"

    def test_reviewer_username_returns_forgejo_org_override(self):
        resolver = _resolver(
            platform_prefix="FORGEJO",
            FORGEJO_TOKEN_myorg_REVIEWER_USERNAME="fj-user",
        )
        assert resolver.reviewer_username("myorg/repo") == "fj-user"

    def test_github_and_forgejo_prefixes_are_independent(self):
        gh = _resolver(GITHUB_TOKEN_myorg_OWNER="gh-tok")
        fj = _resolver(platform_prefix="FORGEJO", FORGEJO_TOKEN_myorg_OWNER="fj-tok")
        assert gh.resolve("OWNER", "myorg/repo") == "gh-tok"
        assert fj.resolve("OWNER", "myorg/repo") == "fj-tok"
