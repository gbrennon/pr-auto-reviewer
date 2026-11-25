"""Parse organization- and repository-specific platform tokens."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.config.org_token_entry import OrgTokenEntry
from pr_auto_reviewer.infrastructure.config.org_token_overrides import (
    OrgTokenOverrides,
    decode_repository_key,
)
from pr_auto_reviewer.infrastructure.config.role_suffix_parser import RoleSuffixParser


class TokenOverridesParser:
    """Build organization and repository token overrides from environment values."""

    def parse(self, source: dict[str, str]) -> OrgTokenOverrides:
        """Parse GitHub and Forgejo token variables."""
        repositories: dict[str, OrgTokenEntry] = {}
        github = self._parse_platform(source, "GITHUB_TOKEN_", "GITHUB", repositories)
        forgejo = self._parse_platform(source, "FORGEJO_TOKEN_", "FORGEJO", repositories)
        return OrgTokenOverrides(
            github=github,
            forgejo=forgejo,
            repositories=repositories,
        )

    def _parse_platform(
        self,
        source: dict[str, str],
        prefix: str,
        platform: str,
        repositories: dict[str, OrgTokenEntry],
    ) -> dict[str, OrgTokenEntry]:
        entries: dict[str, OrgTokenEntry] = {}
        for key, value in source.items():
            if not key.startswith(prefix):
                continue
            organization, role = RoleSuffixParser.parse(key[len(prefix) :])
            if not organization or not role:
                continue
            if organization.startswith("REPO_") and self._parse_repository(
                organization, role, value, platform, repositories
            ):
                continue
            entries[organization] = self._with_role(
                entries.get(organization, OrgTokenEntry()), role, value
            )
        return entries

    def _parse_repository(
        self,
        encoded: str,
        role: str,
        value: str,
        platform: str,
        repositories: dict[str, OrgTokenEntry],
    ) -> bool:
        try:
            identity = decode_repository_key(encoded)
        except ValueError:
            return False
        identity_platform, _, _ = identity.partition(":")
        if identity_platform.upper() != platform:
            return False
        repositories[identity] = self._with_role(
            repositories.get(identity, OrgTokenEntry()), role, value
        )
        return True

    def _with_role(
        self, entry: OrgTokenEntry, role: str, value: str
    ) -> OrgTokenEntry:
        values = {
            "manager_token": entry.manager_token,
            "reviewer_token": entry.reviewer_token,
            "reviewer_username": entry.reviewer_username,
        }
        role_fields = {
            "MANAGER": "manager_token",
            "REVIEWER": "reviewer_token",
            "REVIEWER_USERNAME": "reviewer_username",
        }
        field_name = role_fields.get(role)
        if field_name:
            values[field_name] = value
        return OrgTokenEntry(**values)
