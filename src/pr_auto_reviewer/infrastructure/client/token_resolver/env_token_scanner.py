"""Scans ``os.environ`` for per-organisation token overrides."""

from __future__ import annotations

import logging
import os

from pr_auto_reviewer.infrastructure.client.token_resolver.role_suffix_parser import (
    RoleSuffixParser,
)

logger = logging.getLogger(__name__)


class EnvTokenScanner:
    """Scans an environ dict for ``{PREFIX}_TOKEN_{ORG}_{ROLE}`` overrides.

    Args:
        env_prefix: The prefix to match (e.g. ``"GITHUB_TOKEN_"``).
        environ: Environment dict to scan.  Defaults to ``os.environ``.
    """

    def __init__(
        self, env_prefix: str, *, environ: dict[str, str] | None = None
    ) -> None:
        self._env_prefix = env_prefix
        self._org_tokens: dict[str, dict[str, tuple[str, str]]] = {}
        self._scan(environ if environ is not None else os.environ)

    def tokens_by_org(self) -> dict[str, dict[str, tuple[str, str]]]:
        """Return ``{org: {role: (token, env_var_key)}}``."""
        return self._org_tokens

    def _scan(self, environ: dict[str, str]) -> None:
        for key, value in environ.items():
            if not key.startswith(self._env_prefix):
                continue
            suffix = key[len(self._env_prefix) :]
            org, role = RoleSuffixParser.parse(suffix)
            if org and role:
                self._org_tokens.setdefault(org, {})[role] = (value, key)

        if self._org_tokens:
            logger.info(
                "EnvTokenScanner[%s]: loaded %d org(s) with overrides: %s",
                self._env_prefix,
                len(self._org_tokens),
                sorted(self._org_tokens.keys()),
            )