"""RepoListerPort - port for listing repositories to watch."""

from __future__ import annotations

from abc import ABC, abstractmethod

class RepoListerPort(ABC):
    """Port for listing repositories to watch."""

    @abstractmethod
    def list_repos(self) -> list[str]:
        """List all repositories to monitor.

        Returns:
            Full repo paths: ["owner/repo-a", "owner/repo-b"]
        """
