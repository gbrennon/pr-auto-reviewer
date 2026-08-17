"""Git-repo-lister adapter - lists repositories to watch."""

from __future__ import annotations

import logging

import requests

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.presentation.ports import RepoInfo, RepoListerPort

logger = logging.getLogger(__name__)

class GithubRepoLister(RepoListerPort):
    """Lists repositories owned by the authenticated user."""

    def __init__(self, client: GitPlatformHttpClient, repos_filter: str | None = None) -> None:
        self._client = client
        self._repos_filter = repos_filter

    def list_repos(self) -> list[RepoInfo]:
        """List all repositories accessible to the authenticated user."""
        if self._repos_filter:
            logger.debug("Using REPOS_FILTER=%s, returning singleton", self._repos_filter)
            return [RepoInfo(full_name=self._repos_filter)]
        try:
            data = self._client.get("/user/repos", per_page=100, type="all", sort="updated")
            repos = data if isinstance(data, list) else data.get("data", [])

            result = [
                RepoInfo(full_name=repo["full_name"], pushed_at=repo.get("pushed_at"))
                for repo in repos
                if "full_name" in repo
            ]

            logger.info("GithubRepoLister.list_repos return: %d repos", len(result))
            return result

        except (requests.RequestException, OSError, TypeError) as exc:
            logger.warning("Failed to list repos: %s", exc)
            return []
