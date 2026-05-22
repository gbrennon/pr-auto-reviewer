"""PrListerPort - port for listing and fetching pull requests."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from pr_auto_reviewer.presentation.ports.open_pull_request import OpenPullRequest


class PrListerPort(ABC):
    """Port for listing and fetching pull requests."""

    @abstractmethod
    def list_open(self, repository: str) -> list[OpenPullRequest]:
        """List all open (non-merged) PRs in a repository.

        Args:
            repository: Full repo path (e.g., "owner/repo")

        Returns:
            List of open pull requests.
        """

    @abstractmethod
    def get_pr(self, repository: str, pr_number: int) -> Optional[OpenPullRequest]:
        """Fetch a single PR by number, regardless of state (open/closed/merged).

        Args:
            repository: Full repo path (e.g., "owner/repo")
            pr_number: PR number to fetch

        Returns:
            OpenPullRequest if found, None otherwise.
        """
