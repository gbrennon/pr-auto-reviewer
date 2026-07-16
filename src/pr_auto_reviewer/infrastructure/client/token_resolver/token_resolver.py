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

from typing import ClassVar

from pr_auto_reviewer.infrastructure.client.token_defaults import TokenDefaults
from pr_auto_reviewer.infrastructure.client.token_resolver.env_token_scanner import (
    EnvTokenScanner,
)
from pr_auto_reviewer.infrastructure.client.token_resolver.org_extractor import (
    OrgExtractor,
)
from pr_auto_reviewer.infrastructure.client.token_resolver.token_role_defaults import (
    TokenRoleDefaults,
)


class TokenResolver:
    """Resolves per-org tokens from environment variables.

    Args:
        platform_prefix: ``"GITHUB"`` or ``"FORGEJO"`` — drives the env var
            pattern ``{PREFIX}_TOKEN_{ORG}_{ROLE}``.
        defaults: Fallback tokens when no org override exists.
        scanner: Pre-built ``EnvTokenScanner``.  When omitted a scanner is
            created from ``platform_prefix`` against ``os.environ``.
    """

    _ENV_PREFIX_TEMPLATE: ClassVar[str] = "{prefix}_TOKEN_"

    def __init__(
        self,
        platform_prefix: str,
        defaults: TokenDefaults,
        *,
        scanner: EnvTokenScanner | None = None,
    ) -> None:
        prefix = platform_prefix.upper()
        self._defaults = TokenRoleDefaults(prefix, defaults)
        if scanner is not None:
            self._scanner = scanner
        else:
            env_prefix = self._ENV_PREFIX_TEMPLATE.format(prefix=prefix)
            self._scanner = EnvTokenScanner(env_prefix)

    def resolve(self, role: str, repo: str) -> str:
        """Return the token for *role* scoped to *repo*'s org.

        ``repo`` is a full repository path like ``"my-org/my-repo"``.
        Falls back to the platform default when no org override is set.
        """
        token, _ = self._resolve_with_source(role, repo)
        return token

    def resolve_source(self, role: str, repo: str) -> tuple[str, str]:
        """Return ``(token, env_var_key)`` for *role* scoped to *repo*'s org.

        The *env_var_key* is the exact environment variable name that
        supplied the token (e.g. ``"GITHUB_OWNER_TOKEN"`` or
        ``"GITHUB_TOKEN_forging-blocks-org_OWNER"``).
        """
        return self._resolve_with_source(role, repo)

    def reviewer_username(self, repo: str) -> str:
        """Return the reviewer username for *repo*'s org."""
        org = OrgExtractor.from_repo(repo)
        if not org:
            return self._defaults.reviewer_username()

        org_entry = self._scanner.tokens_by_org().get(org)
        if org_entry and "REVIEWER_USERNAME" in org_entry:
            token, _ = org_entry["REVIEWER_USERNAME"]
            return token

        return self._defaults.reviewer_username()

    def _resolve_with_source(self, role: str, repo: str) -> tuple[str, str]:
        org = OrgExtractor.from_repo(repo)
        if not org:
            return self._defaults.token_for(role), self._defaults.source_key_for(role)

        org_entry = self._scanner.tokens_by_org().get(org)
        role_upper = role.upper()
        if org_entry and role_upper in org_entry:
            token, source_key = org_entry[role_upper]
            return token, source_key

        return self._defaults.token_for(role), self._defaults.source_key_for(role)