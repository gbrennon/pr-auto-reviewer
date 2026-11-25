"""Token overrides scoped to organizations and full repositories."""

from __future__ import annotations

from dataclasses import dataclass, field

from pr_auto_reviewer.infrastructure.config.org_token_entry import OrgTokenEntry

_REPOSITORY_KEY_PREFIX = "REPO_"


def encode_repository_key(identity: str) -> str:
    """Encode a ``platform:owner/repo`` identity for use in secret names."""
    _validate_repository_identity(identity)
    return f"{_REPOSITORY_KEY_PREFIX}{identity.encode('utf-8').hex()}"


def decode_repository_key(encoded: str) -> str:
    """Decode a canonical repository identity key."""
    if not encoded.startswith(_REPOSITORY_KEY_PREFIX):
        raise ValueError("Repository key has an invalid prefix")
    value = encoded[len(_REPOSITORY_KEY_PREFIX) :]
    if not value:
        raise ValueError("Repository key is empty")
    try:
        identity = bytes.fromhex(value).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("Repository key is not valid hexadecimal UTF-8") from error
    _validate_repository_identity(identity)
    return identity


def _validate_repository_identity(identity: str) -> None:
    platform, separator, repository = identity.partition(":")
    owner, owner_separator, name = repository.partition("/")
    if (
        not separator
        or not platform
        or not owner_separator
        or not owner
        or not name
        or ":" in platform
    ):
        raise ValueError("Repository identity must be platform:owner/repo")


@dataclass(frozen=True)
class OrgTokenOverrides:
    github: dict[str, OrgTokenEntry] = field(default_factory=dict)
    forgejo: dict[str, OrgTokenEntry] = field(default_factory=dict)
    repositories: dict[str, OrgTokenEntry] = field(default_factory=dict)
