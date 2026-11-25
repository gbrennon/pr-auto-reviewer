"""Tests for owner and repository token override parsing."""

import pytest

from pr_auto_reviewer.infrastructure.config.org_token_overrides import (
    decode_repository_key,
    encode_repository_key,
)
from pr_auto_reviewer.infrastructure.config.token_overrides_parser import (
    TokenOverridesParser,
)


@pytest.mark.parametrize(
    "identity",
    (
        "github:owner/repo",
        "forgejo:owner_with_underscore/repo_with_underscore",
        "github:owner_repo/repo_name",
    ),
)
def test_repository_key_round_trips(identity: str) -> None:
    encoded = encode_repository_key(identity)

    assert decode_repository_key(encoded) == identity


def test_repository_key_encoding_does_not_collide_on_underscores() -> None:
    first = encode_repository_key("github:owner/repo_name")
    second = encode_repository_key("github:owner_repo/name")

    assert first != second


def test_parser_keeps_owner_overrides_compatible() -> None:
    overrides = TokenOverridesParser().parse(
        {
            "GITHUB_TOKEN_my_org_MANAGER": "OWNER_MANAGER",
            "GITHUB_TOKEN_my_org_REVIEWER": "OWNER_REVIEWER",
        }
    )

    assert overrides.github["my_org"].manager_token == "OWNER_MANAGER"
    assert overrides.github["my_org"].reviewer_token == "OWNER_REVIEWER"


def test_parser_keeps_legacy_owner_names_with_repository_prefix() -> None:
    overrides = TokenOverridesParser().parse(
        {"GITHUB_TOKEN_REPO_owner_MANAGER": "OWNER_MANAGER"}
    )

    assert overrides.github["REPO_owner"].manager_token == "OWNER_MANAGER"


def test_parser_reads_repository_role_entries_independently() -> None:
    identity = "github:my_org/repo_name"
    encoded = encode_repository_key(identity)
    overrides = TokenOverridesParser().parse(
        {
            f"GITHUB_TOKEN_{encoded}_MANAGER": "REPOSITORY_MANAGER",
            f"GITHUB_TOKEN_{encoded}_REVIEWER": "REPOSITORY_REVIEWER",
        }
    )

    entry = overrides.repositories[identity]
    assert entry.manager_token == "REPOSITORY_MANAGER"
    assert entry.reviewer_token == "REPOSITORY_REVIEWER"
