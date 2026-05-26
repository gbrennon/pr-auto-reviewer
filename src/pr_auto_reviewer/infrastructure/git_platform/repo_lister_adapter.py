"""Git-repo-lister adapter - lists repositories to watch."""

from __future__ import annotations

import logging

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.presentation.ports import RepoListerPort

logger = logging.getLogger(__name__)


class GitRepoListerAdapter(RepoListerPort):
    """Lists repositories owned by the authenticated user."""

    def __init__(self, client: GitPlatformHttpClient, repos_filter: str | None = None) -> None:
        self._client = client
        self._repos_filter = repos_filter

    def list_repos(self) -> list[str]:
        """List all repositories owned by the authenticated user."""
        if self._repos_filter:
            logger.debug("Using REPOS_FILTER=%s, returning singleton", self._repos_filter)
            return [self._repos_filter]
        try:
            logger.debug("Fetching user info to list repos")
            user_data = self._client.get("/user")
            username = user_data.get("login") or user_data.get("username")
            if not username:
                logger.warning("Could not determine username from /user response")
                return []

            data = self._client.get("/user/repos", limit=50)
            repos = data if isinstance(data, list) else data.get("data", [])

            def is_owned(repo: dict) -> bool:
                full_name = repo.get("full_name", "")
                owner = repo.get("owner", {})
                if isinstance(owner, dict):
                    repo_owner = owner.get("login") or owner.get("username") or ""
                else:
                    repo_owner = ""
                return full_name.startswith(f"{username}/") or repo_owner == username

            result = [
                repo["full_name"]
                for repo in repos
                if "full_name" in repo and is_owned(repo)
            ]

            if self._repos_filter:
                result = [r for r in result if self._repos_filter in r]

            logger.debug("Found %d owned repos%s", len(result),
                         f" (filtered by '{self._repos_filter}')" if self._repos_filter else "")
            logger.info("GitRepoListerAdapter.list_repos return: %s", result)
            return result

        except Exception as exc:
            logger.warning("Failed to list repos: %s", exc)
            return []
