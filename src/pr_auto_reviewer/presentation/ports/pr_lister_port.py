"""PrListerPort - port for listing open pull requests in a repository."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pr_auto_reviewer.presentation.ports.open_pull_request import OpenPullRequest


class PrListerPort(ABC):
    """Port for listing open pull requests in a repository."""

    @abstractmethod
    def list_open(self, repository: str) -> list[OpenPullRequest]:
        """List all open (non-merged) PRs in a repository.

        Args:
            repository: Full repo path (e.g., "owner/repo")

        Returns:
            List of open pull requests.
        """