"""Fake GithubIssueTracker for tests - exercises all code paths."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.issue_tracker_port import (
    IssueTrackerPort,
)
from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class FakeGithubIssueTracker(IssueTrackerPort):
    """Fake GithubIssueTracker that tracks create calls without making HTTP calls."""

    def __init__(self) -> None:
        self._issues: list[Issue] = []
        self.create_calls: list[tuple[str, str, str, str]] = []

    def create(
        self, repository: str, title: str, body: str, source_item_id: str = ""
    ) -> Issue:
        """Store fake issue without making HTTP calls."""
        self.create_calls.append((repository, title, body, source_item_id))
        issue_number = len(self._issues) + 1
        issue = Issue(
            id=issue_number,
            repository=repository,
            title=title,
            body=body,
            source_pr_id=PullRequestId(repository=repository, number=1),
            source_item_id=source_item_id,
        )
        self._issues.append(issue)
        return issue

    def simulate_error(self, repository: str, title: str, body: str) -> None:
        """Simulate a create error for testing error handling."""
        raise Exception("Simulated API error")