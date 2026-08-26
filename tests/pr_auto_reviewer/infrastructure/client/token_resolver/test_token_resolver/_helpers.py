"""Shared helpers, fixtures, and imports for the split test modules."""

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


__all__ = ['EnvTokenScanner', 'TokenDefaults', 'TokenResolver', '_resolver']
