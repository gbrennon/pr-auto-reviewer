"""Tests for TokenResolver source resolution behavior."""

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


class TestTokenResolverResolveSource:
    def test_resolve_source_returns_default_key_when_no_override(self):
        resolver = _resolver()
        _, source = resolver.resolve_source("OWNER", "myorg/repo")
        assert source == "GITHUB_OWNER_TOKEN"

    def test_resolve_source_returns_org_env_var_key(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_OWNER="org-tok")
        _, source = resolver.resolve_source("OWNER", "myorg/repo")
        assert source == "GITHUB_TOKEN_myorg_OWNER"
