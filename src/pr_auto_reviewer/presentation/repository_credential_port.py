"""Repository credential presentation port."""

from __future__ import annotations

from typing import Protocol


class RepositoryCredentialPort(Protocol):
    """Manage optional repository-specific role credentials."""

    def save_repository_credentials(
        self,
        repository: str,
        manager_token: str,
        reviewer_token: str,
    ) -> None:
        """Set or clear optional repository-specific role credentials."""
        ...
