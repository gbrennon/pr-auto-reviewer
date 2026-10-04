"""Git-repo-lister adapter - lists repositories to watch."""

from __future__ import annotations

import logging

from typing import cast

import requests

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.presentation.ports import RepoInfo, RepoListerPort

logger = logging.getLogger(__name__)

_REPOSITORY_PAGE_SIZE = 50


class ForgejoRepoLister(RepoListerPort):
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
            return self._fetch_repository_pages()
        except (requests.RequestException, OSError, TypeError, KeyError) as exc:
            logger.warning("Failed to list repos: %s", exc)
            return []

    def _fetch_repository_pages(self) -> list[RepoInfo]:
        repositories: list[RepoInfo] = []
        page = 1
        while True:
            rows = self._fetch_repository_page(page)
            repositories.extend(self._parse_repositories(rows))
            if len(rows) < _REPOSITORY_PAGE_SIZE:
                return repositories
            page += 1

    def _fetch_repository_page(self, page: int) -> list[dict[str, object]]:
        payload: object = self._client.get(
            "/user/repos",
            limit=_REPOSITORY_PAGE_SIZE,
            page=page,
            type="all",
            sort="updated",
        )
        raw_rows = payload if isinstance(payload, list) else payload.get("data", [])
        return [cast(dict[str, object], row) for row in raw_rows if isinstance(row, dict)]

    def _parse_repositories(self, rows: list[dict[str, object]]) -> list[RepoInfo]:
        return [
            parsed
            for row in rows
            if (parsed := self._parse_repository(row)) is not None
        ]

    def _parse_repository(self, row: dict[str, object]) -> RepoInfo | None:
        full_name = row.get("full_name")
        pushed_at = row.get("pushed_at")
        if not isinstance(full_name, str):
            return None
        if pushed_at is not None and not isinstance(pushed_at, str):
            return None
        return RepoInfo(full_name=full_name, pushed_at=pushed_at)
