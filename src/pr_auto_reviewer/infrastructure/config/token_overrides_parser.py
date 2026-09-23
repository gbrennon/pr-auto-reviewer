"""Parse organization-specific platform tokens."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.config.org_token_entry import OrgTokenEntry
from pr_auto_reviewer.infrastructure.config.org_token_overrides import OrgTokenOverrides
from pr_auto_reviewer.infrastructure.config.role_suffix_parser import RoleSuffixParser


class TokenOverridesParser:
    """Build organization token overrides from environment values."""

    def parse(self, source: dict[str, str]) -> OrgTokenOverrides:
        """Parse GitHub and Forgejo organization token variables."""
        github = self._parse_platform(source, "GITHUB_TOKEN_")
        forgejo = self._parse_platform(source, "FORGEJO_TOKEN_")
        return OrgTokenOverrides(github=github, forgejo=forgejo)

    def _parse_platform(
        self, source: dict[str, str], prefix: str
    ) -> dict[str, OrgTokenEntry]:
        entries: dict[str, OrgTokenEntry] = {}
        for key, value in source.items():
            if not key.startswith(prefix):
                continue
            organization, role = RoleSuffixParser.parse(key[len(prefix):])
            if organization and role:
                entries[organization] = self._with_role(
                    entries.get(organization, OrgTokenEntry()), role, value
                )
        return entries

    def _with_role(
        self, entry: OrgTokenEntry, role: str, value: str
    ) -> OrgTokenEntry:
        values = {
            "owner_token": entry.owner_token,
            "reviewer_token": entry.reviewer_token,
            "reviewer_username": entry.reviewer_username,
        }
        role_fields = {
            "OWNER": "owner_token",
            "REVIEWER": "reviewer_token",
            "REVIEWER_USERNAME": "reviewer_username",
        }
        field_name = role_fields.get(role)
        if field_name:
            values[field_name] = value
        return OrgTokenEntry(**values)
