"""Maps role names to platform default tokens and their env var keys."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.client.token_defaults import TokenDefaults


class TokenRoleDefaults:
    """Maps role names to platform default tokens and their env var keys."""

    def __init__(self, platform_prefix: str, defaults: TokenDefaults) -> None:
        self._prefix = platform_prefix.upper()
        self._defaults = defaults

    def token_for(self, role: str) -> str:
        role_upper = role.upper()
        if role_upper == "OWNER":
            return self._defaults.owner_token
        if role_upper == "REVIEWER":
            return self._defaults.reviewer_token
        return ""

    def source_key_for(self, role: str) -> str:
        """Return the env var key for the platform default of *role*."""
        return f"{self._prefix}_{role.upper()}_TOKEN"

    def reviewer_username(self) -> str:
        return self._defaults.reviewer_username
