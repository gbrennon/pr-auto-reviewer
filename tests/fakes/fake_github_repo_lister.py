"""Fake GithubRepoLister for tests - exercises all code paths."""

from __future__ import annotations

from pr_auto_reviewer.presentation.ports import RepoInfo


class FakeGithubRepoLister:
    """Fake GithubRepoLister that returns pre-configured repos without making HTTP calls."""

    def __init__(self) -> None:
        self.list_repos_calls: list[str] = []
        self.get_repo_calls: list[tuple[str, str]] = []

    def _default_repos(self) -> list[RepoInfo]:
        return [self._default_repo()]

    def _default_repo(self) -> RepoInfo:
        return RepoInfo(
            full_name="owner/test-repo",
            pushed_at="2024-01-01T00:00:00Z",
        )

    def list_repos(self, username: str) -> list[RepoInfo]:
        """Return fake repos without making HTTP calls."""
        self.list_repos_calls.append(username)
        return self._default_repos()

    def get_repo(self, full_name: str, ref: str = "main") -> RepoInfo | None:
        """Return fake repo by name without making HTTP calls."""
        self.get_repo_calls.append((full_name, ref))
        if full_name == "owner/test-repo":
            return self._default_repo()
        return None

    def simulate_error_list_repos(self) -> None:
        """Simulate an error in list_repos for testing."""
        raise Exception("Simulated GitHub API error")

    def simulate_error_get_repo(self) -> None:
        """Simulate an error in get_repo for testing."""
        raise Exception("Simulated GitHub API error")