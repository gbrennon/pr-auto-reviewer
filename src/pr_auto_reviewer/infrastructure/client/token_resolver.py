"""TokenResolver — resolves per-org platform tokens from env vars.

Scans environment variables matching ``{PREFIX}_TOKEN_{ORG}_{ROLE}`` and
falls back to default tokens when no org-specific override exists.

    GITHUB_TOKEN_my-org_OWNER=ghp_...
    GITHUB_TOKEN_my-org_REVIEWER=ghp_...
    GITHUB_TOKEN_my-org_REVIEWER_USERNAME=my-bot

Resolution order per role: org override → default → "".

Org names may contain underscores — the role is identified by suffix-matching
against known roles (``REVIEWER_USERNAME``, ``REVIEWER``, ``OWNER``) in
longest-first order, eliminating ambiguity without a double-underscore
convention.
"""

from __future__ import annotations

import logging
import os
from typing import ClassVar

from pr_auto_reviewer.infrastructure.client.token_defaults import TokenDefaults


logger = logging.getLogger(__name__)

_ROLES: tuple[str, ...] = ("REVIEWER_USERNAME", "REVIEWER", "OWNER")

class TokenResolver:
    """Resolves per-org tokens from environment variables.

    Args:
        platform_prefix: ``"GITHUB"`` or ``"FORGEJO"`` — drives the env var
            pattern ``{PREFIX}_TOKEN_{ORG}_{ROLE}``.
        defaults: Fallback tokens when no org override exists.
    """

    _ENV_PREFIX_TEMPLATE: ClassVar[str] = "{prefix}_TOKEN_"

    def __init__(self, platform_prefix: str, defaults: TokenDefaults) -> None:
        self._prefix = platform_prefix.upper()
        self._defaults = defaults
        self._org_tokens: dict[str, dict[str, str]] = {}
        self._env_prefix = self._ENV_PREFIX_TEMPLATE.format(prefix=self._prefix)
        self._scan_env()


    def resolve(self, role: str, repo: str) -> str:
        """Return the token for *role* scoped to *repo*'s org.

        ``repo`` is a full repository path like ``"my-org/my-repo"``.
        Falls back to the platform default when no org override is set.
        """
        org = self._extract_org(repo)
        if not org:
            return self._default_for(role)

        org_entry = self._org_tokens.get(org)
        role_upper = role.upper()
        if org_entry and role_upper in org_entry:
            return org_entry[role_upper]

        return self._default_for(role)

    def reviewer_username(self, repo: str) -> str:
        """Return the reviewer username for *repo*'s org."""
        org = self._extract_org(repo)
        if not org:
            return self._defaults.reviewer_username

        org_entry = self._org_tokens.get(org)
        if org_entry and "REVIEWER_USERNAME" in org_entry:
            return org_entry["REVIEWER_USERNAME"]

        return self._defaults.reviewer_username


    @staticmethod
    def _extract_org(repo: str) -> str:
        """Return the org portion of ``"org/repo"``, or ``""``."""
        if "/" in repo:
            return repo.split("/", 1)[0]
        return ""

    def _default_for(self, role: str) -> str:
        """Map a role string to the corresponding default token."""
        role_upper = role.upper()
        if role_upper == "OWNER":
            return self._defaults.owner_token
        if role_upper == "REVIEWER":
            return self._defaults.reviewer_token
        return ""

    def _scan_env(self) -> None:
        """Scan ``os.environ`` for ``{PREFIX}_TOKEN_{ORG}_{ROLE}`` vars."""
        for key, value in os.environ.items():
            if not key.startswith(self._env_prefix):
                continue
            suffix = key[len(self._env_prefix):]
            org, role = self._parse_org_role(suffix)
            if org and role:
                self._org_tokens.setdefault(org, {})[role] = value

        if self._org_tokens:
            logger.info(
                "TokenResolver[%s]: loaded %d org(s) with overrides: %s",
                self._prefix,
                len(self._org_tokens),
                sorted(self._org_tokens.keys()),
            )

    @staticmethod
    def _parse_org_role(suffix: str) -> tuple[str, str]:
        """Parse ``{org}_{ROLE}`` suffix into ``(org, role)``.

        Tries each known role as a suffix in longest-first order, then
        strips the separator underscore.  Returns ``("", "")`` when no
        role is recognised.
        """
        for role in _ROLES:
            role_suffix = f"_{role}"
            if suffix.endswith(role_suffix) and len(suffix) > len(role_suffix):
                return suffix[:-len(role_suffix)], role
        return "", ""
