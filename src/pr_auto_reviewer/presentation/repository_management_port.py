"""Repository management presentation port."""

from __future__ import annotations

from typing import Protocol

from pr_auto_reviewer.presentation.settings_models import RepositoryCredentialStatus


class RepositoryManagementPort(Protocol):
    """Manage registered repositories and credential source status."""

    def list_repositories(self) -> tuple[RepositoryCredentialStatus, ...]:
        """Return repositories and per-role credential sources."""
        ...

    def add_repository(self, repository: str) -> None:
        """Register a repository without requiring credentials."""
        ...

    def remove_repository(self, repository: str) -> None:
        """Remove a repository from the allow list."""
        ...
