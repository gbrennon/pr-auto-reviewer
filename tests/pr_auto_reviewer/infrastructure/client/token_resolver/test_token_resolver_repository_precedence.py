"""Tests for repository-specific token precedence."""

from pr_auto_reviewer.infrastructure.client.token_defaults import TokenDefaults
from pr_auto_reviewer.infrastructure.client.token_resolver import TokenResolver
from pr_auto_reviewer.infrastructure.client.token_resolver.env_token_scanner import (
    EnvTokenScanner,
)
from pr_auto_reviewer.infrastructure.config.org_token_overrides import (
    encode_repository_key,
)
from pr_auto_reviewer.infrastructure.config.token_overrides_parser import (
    TokenOverridesParser,
)


def _resolver(source: dict[str, str]) -> TokenResolver:
    defaults = TokenDefaults(
        manager_token="GLOBAL_MANAGER",
        reviewer_token="GLOBAL_REVIEWER",
    )
    return TokenResolver(
        "GITHUB",
        defaults,
        scanner=EnvTokenScanner("GITHUB_TOKEN_", environ=source),
        overrides=TokenOverridesParser().parse(source),
    )


def test_repository_manager_and_reviewer_entries_beat_owner_and_global() -> None:
    identity = "github:my_org/repo_name"
    encoded = encode_repository_key(identity)
    source = {
        "GITHUB_TOKEN_my_org_MANAGER": "OWNER_MANAGER",
        "GITHUB_TOKEN_my_org_REVIEWER": "OWNER_REVIEWER",
        f"GITHUB_TOKEN_{encoded}_MANAGER": "REPOSITORY_MANAGER",
        f"GITHUB_TOKEN_{encoded}_REVIEWER": "REPOSITORY_REVIEWER",
    }
    resolver = _resolver(source)

    assert resolver.resolve("MANAGER", "my_org/repo_name") == "REPOSITORY_MANAGER"
    assert resolver.resolve("REVIEWER", "my_org/repo_name") == "REPOSITORY_REVIEWER"


def test_missing_repository_role_falls_back_independently() -> None:
    identity = "github:my_org/repo_name"
    encoded = encode_repository_key(identity)
    source = {
        "GITHUB_TOKEN_my_org_REVIEWER": "OWNER_REVIEWER",
        f"GITHUB_TOKEN_{encoded}_MANAGER": "REPOSITORY_MANAGER",
    }
    resolver = _resolver(source)

    assert resolver.resolve("MANAGER", "my_org/repo_name") == "REPOSITORY_MANAGER"
    assert resolver.resolve("REVIEWER", "my_org/repo_name") == "OWNER_REVIEWER"


def test_missing_repository_and_owner_role_uses_global_independently() -> None:
    identity = "github:my_org/repo_name"
    encoded = encode_repository_key(identity)
    source = {f"GITHUB_TOKEN_{encoded}_MANAGER": "REPOSITORY_MANAGER"}
    resolver = _resolver(source)

    assert resolver.resolve("MANAGER", "my_org/repo_name") == "REPOSITORY_MANAGER"
    assert resolver.resolve("REVIEWER", "my_org/repo_name") == "GLOBAL_REVIEWER"


def test_repository_source_key_identifies_the_specific_role_entry() -> None:
    identity = "github:my_org/repo_name"
    encoded = encode_repository_key(identity)
    source_key = f"GITHUB_TOKEN_{encoded}_MANAGER"
    resolver = _resolver({source_key: "REPOSITORY_MANAGER"})

    _, source = resolver.resolve_source("MANAGER", "my_org/repo_name")

    assert source == source_key
