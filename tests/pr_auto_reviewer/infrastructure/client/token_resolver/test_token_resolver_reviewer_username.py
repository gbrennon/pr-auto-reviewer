"""Tests for TokenResolver reviewer username behavior."""

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


class TestTokenResolverReviewerUsername:
    def test_reviewer_username_returns_default(self):
        resolver = _resolver()
        assert resolver.reviewer_username("myorg/repo") == "default-username"

    def test_reviewer_username_returns_org_override(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_REVIEWER_USERNAME="org-user")
        assert resolver.reviewer_username("myorg/repo") == "org-user"
