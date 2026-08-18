"""Fake GithubPrLister for tests - exercises all code paths."""

from __future__ import annotations

from pr_auto_reviewer.presentation.ports import PrListerPort
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.ports import OpenPullRequest


class FakeGithubPrLister(PrListerPort):
    """Fake GithubPrLister that returns pre-configured PRs without making HTTP calls."""

    def __init__(self, prs: list[OpenPullRequest] | None = None) -> None:
        self._prs = prs or self._default_prs()
        self.list_open_calls: list[str] = []
        self.get_pr_calls: list[tuple[str, int]] = []

    def _default_prs(self) -> list[OpenPullRequest]:
        return [
            OpenPullRequest(
                pr_id=PullRequestId(repository="owner/repo", number=1),
                head_sha=CommitSha("abc123"),
                title="Test PR 1",
                description="Test description 1",
                is_draft=False,
                review_requested=False,
                target_branch="main",
            ),
            OpenPullRequest(
                pr_id=PullRequestId(repository="owner/repo", number=2),
                head_sha=CommitSha("def456"),
                title="Test PR 2",
                description="Test description 2",
                is_draft=False,
                review_requested=True,
                target_branch="feature",
            ),
        ]

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        """Return fake PRs without making HTTP calls."""
        self.list_open_calls.append(repository)
        return list(self._prs)

    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
        """Return fake PR by number without making HTTP calls."""
        self.get_pr_calls.append((repository, pr_number))
        for pr in self._prs:
            if pr.pr_id.number == pr_number:
                return pr
        return None

    def simulate_error_list_open(self) -> None:
        """Simulate an error in list_open for testing."""
        raise Exception("Simulated Forgejo API error")

    def simulate_error_get_pr(self) -> None:
        """Simulate an error in get_pr for testing."""
        raise Exception("Simulated Forgejo API error")