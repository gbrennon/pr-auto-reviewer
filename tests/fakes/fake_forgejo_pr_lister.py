"""Fake ForgejoPrLister for tests."""

from __future__ import annotations

from typing import Any

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.ports import OpenPullRequest


class FakeForgejoPrLister:
    """Fake ForgejoPrLister that returns pre-configured PRs without making HTTP calls."""

    def __init__(
        self,
        prs: list[OpenPullRequest] | None = None,
    ) -> None:
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
        # Return the first PR with matching number, or None if not found
        for pr in self._prs:
            if pr.pr_id.number == pr_number:
                return pr
        return None


class FakeForgejoPrListerWithError:
    """Fake ForgejoPrLister that can simulate errors."""

    def __init__(self, should_fail: bool = False) -> None:
        self._should_fail = should_fail
        self.list_open_calls: list[str] = []
        self.get_pr_calls: list[tuple[str, int]] = []

    def list_open(self, repository: str) -> list[Any]:
        """Simulate listing PRs, optionally failing."""
        self.list_open_calls.append(repository)
        if self._should_fail:
            raise Exception("Simulated Forgejo API error")
        return []

    def get_pr(self, repository: str, pr_number: int) -> Any | None:
        """Simulate fetching PR, optionally failing."""
        self.get_pr_calls.append((repository, pr_number))
        if self._should_fail:
            raise Exception("Simulated Forgejo API error")
        return None