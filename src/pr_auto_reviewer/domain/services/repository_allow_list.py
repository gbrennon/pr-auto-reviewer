"""RepositoryAllowList - decides which repositories are eligible for review."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class RepositoryAllowList:
    """Eligibility rule over repository full names.

    Matching is case-insensitive. Supports platform-prefixed entries
    (e.g. ``github:owner/repo``, ``forgejo:owner/repo``, ``codeberg:owner/repo``)
    and bare ``owner/repo`` entries that match across platforms.
    ``codeberg`` is normalized to ``forgejo``.
    An empty allow list allows every repository.
    """

    allowed_repositories: frozenset[str]

    @classmethod
    def allowing_every_repository(cls) -> RepositoryAllowList:
        """Create an allow list that permits every repository."""
        return cls(allowed_repositories=frozenset())

    @classmethod
    def from_entries(cls, entries: Iterable[str]) -> RepositoryAllowList:
        """Construct an allow list from raw entry strings."""
        return cls(
            allowed_repositories=frozenset(
                cls._normalize_entry(entry)
                for entry in entries
                if entry.strip()
            )
        )

    @classmethod
    def _normalize_entry(cls, raw: str) -> str:
        """Normalize case and platform alias."""
        normalized = raw.strip().casefold()
        if normalized.startswith("codeberg:"):
            return f"forgejo:{normalized.removeprefix('codeberg:')}"
        return normalized

    @property
    def allows_every_repository(self) -> bool:
        """Check whether all repositories are unconditionally permitted."""
        return not self.allowed_repositories

    def allows(self, repository_full_name: str) -> bool:
        """Decide whether *repository_full_name* is permitted."""
        if self.allows_every_repository:
            return True

        normalized = self._normalize_entry(repository_full_name)
        if not normalized:
            return False

        if normalized in self.allowed_repositories:
            return True

        return self._matches_cross_platform(normalized)

    def _matches_cross_platform(self, normalized_name: str) -> bool:
        """Check cross-platform fallback rules for prefixed and bare names."""
        if ":" in normalized_name:
            _, _, bare_repo = normalized_name.partition(":")
            return bare_repo in self.allowed_repositories

        return any(
            entry.endswith(f":{normalized_name}")
            for entry in self.allowed_repositories
        )
