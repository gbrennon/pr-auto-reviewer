"""Parses env var suffixes to identify organisation and role."""

from __future__ import annotations

_ROLES: tuple[str, ...] = ("REVIEWER_USERNAME", "REVIEWER", "OWNER")


class RoleSuffixParser:
    """Parses env var suffixes to identify organisation and role.

    Tries each known role as a suffix in longest-first order, then strips
    the separator underscore. Returns ``("", "")`` when no role is recognised.
    """

    @classmethod
    def parse(cls, suffix: str) -> tuple[str, str]:
        for role in _ROLES:
            role_suffix = f"_{role}"
            if suffix.endswith(role_suffix) and len(suffix) > len(role_suffix):
                return suffix[: -len(role_suffix)], role
        return "", ""
