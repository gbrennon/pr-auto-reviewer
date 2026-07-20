"""RepoListerPort - port for listing repositories to watch."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pr_auto_reviewer.presentation.ports.repo_info import RepoInfo


class RepoListerPort(ABC):
    """Port for listing repositories to watch."""

    @abstractmethod
    def list_repos(self) -> list[RepoInfo]:
        """List all repositories to monitor.

        Returns:
            RepoInfo objects with full_name and pushed_at fields.
        """
