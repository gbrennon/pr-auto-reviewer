"""Integration tests for repo_lister_adapter.py — uses live Codeberg API.

All tests share a session-scoped ``repo_list`` fixture so the live API
is only called once across the entire test session.  See the project
root PERFORMANCE_NOTES.md for rationale.
"""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.git_platform.repo_lister_adapter import (
    GitRepoListerAdapter,
)


class TestGitRepoListerAdapterIntegration:
    """Integration tests for GitRepoListerAdapter against live API."""

    def test_list_repos_returns_non_empty_list(
        self, repo_list: list[str], user_fixtures: dict
    ) -> None:
        """Returned list is non-empty and every entry is owner/repo."""
        assert isinstance(repo_list, list)
        assert len(repo_list) > 0, (
            "Expected at least one repo owned by authenticated user"
        )

        assert all(isinstance(r, str) for r in repo_list)
        assert all("/" in r for r in repo_list), (
            "all repos should be owner/repo format"
        )

    def test_list_repos_all_owned_by_authenticated_user(
        self, repo_list: list[str], user_fixtures: dict
    ) -> None:
        """All returned repos are owned by the authenticated user."""
        username = (
            user_fixtures.get("login")
            or user_fixtures.get("username")
        )

        if username:
            assert all(r.split("/")[0] == username for r in repo_list), (
                f"all repos must be owned by {username}"
            )

    def test_list_repos_with_filter_short_circuits(
        self, repo_lister_adapter: GitRepoListerAdapter, user_fixtures: dict
    ) -> None:
        """When repos_filter is set, only that repo is returned (no API call)."""
        username = (
            user_fixtures.get("login")
            or user_fixtures.get("username")
            or "gbrennon"
        )

        filtered = GitRepoListerAdapter(
            client=repo_lister_adapter._client,
            repos_filter=f"{username}/BitPill",
        )

        result = filtered.list_repos()
        assert len(result) == 1
        assert result[0] == f"{username}/BitPill"

    def test_list_repos_returns_consistent_type(
        self, repo_list: list[str]
    ) -> None:
        """The cached result is a plain list."""
        assert isinstance(repo_list, list)
        assert isinstance(repo_list, list)
