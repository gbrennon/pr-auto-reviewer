"""Tests for CompositeIssueTracker using stub port implementations."""

import pytest

from pr_auto_reviewer.application.ports.outbound.issue_tracker_port import (
    IssueTrackerPort,
)
from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_issue_tracker import (
    CompositeIssueTracker,
)


_SOURCE_PR = PullRequestId(repository="owner/repo", number=1)


class _StubIssueTracker(IssueTrackerPort):
    """Stub tracker that records calls and returns canned issues."""

    def __init__(self, platform_id: int) -> None:
        self.create_calls: list[tuple[str, str, str]] = []
        self._next_id = platform_id

    def create(self, repository: str, title: str, body: str) -> Issue:
        self.create_calls.append((repository, title, body))
        return Issue(
            id=self._next_id,
            repository=repository,
            title=title,
            body=body,
            source_pr_id=_SOURCE_PR,
            source_item_number=1,
        )


class TestCompositeIssueTracker:
    def test_create_routes_to_correct_platform(self):
        github_tracker = _StubIssueTracker(platform_id=100)
        forgejo_tracker = _StubIssueTracker(platform_id=200)
        composite = CompositeIssueTracker({
            "github": github_tracker,
            "forgejo": forgejo_tracker,
        })

        gh_issue = composite.create(
            "github:owner/repo", "bug title", "bug body"
        )
        fj_issue = composite.create(
            "codeberg:org/proj", "feat title", "feat body"
        )

        assert gh_issue.id == 100
        assert gh_issue.repository == "owner/repo"
        assert fj_issue.id == 200
        assert fj_issue.repository == "org/proj"
        assert len(github_tracker.create_calls) == 1
        assert github_tracker.create_calls[0][0] == "owner/repo"
        assert len(forgejo_tracker.create_calls) == 1
        assert forgejo_tracker.create_calls[0][0] == "org/proj"

    def test_create_defaults_to_forgejo_without_prefix(self):
        forgejo_tracker = _StubIssueTracker(platform_id=300)
        composite = CompositeIssueTracker({"forgejo": forgejo_tracker})

        issue = composite.create("owner/repo", "title", "body")

        assert issue.id == 300
        assert issue.repository == "owner/repo"
        assert len(forgejo_tracker.create_calls) == 1
        assert forgejo_tracker.create_calls[0][0] == "owner/repo"

    def test_create_raises_for_unknown_platform(self):
        composite = CompositeIssueTracker({})

        with pytest.raises(ValueError, match="No issue tracker for platform"):
            composite.create("unknown:owner/repo", "title", "body")
