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
            return self._parse_repositories(data)

        except (requests.RequestException, OSError, TypeError) as exc:
            logger.warning("Failed to list repos: %s", exc)
            return []

    def _parse_repositories(self, data: object) -> list[RepoInfo]:
        return [
            parsed
            for row in self._repository_rows(data)
            if (parsed := self._parse_repository(row)) is not None
        ]

    def _repository_rows(self, data: object) -> list[dict[str, object]]:
        rows = data if isinstance(data, list) else data.get("data", [])
        return [row for row in rows if isinstance(row, dict)]

    def _parse_repository(self, row: dict[str, object]) -> RepoInfo | None:
        full_name = row.get("full_name")
        if not isinstance(full_name, str):
            return None
        pushed_at = row.get("pushed_at")
        return RepoInfo(
            full_name=full_name,
            pushed_at=pushed_at if isinstance(pushed_at, str) else None,
        )
