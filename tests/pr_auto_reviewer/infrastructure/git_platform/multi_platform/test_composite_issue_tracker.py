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


class _StubIssueTracker(IssueTrackerPort):
    def __init__(self, platform_id: int) -> None:
        self.create_calls: list[
            tuple[str, str, str, PullRequestId, str]
        ] = []
        self._next_id = platform_id

    def create(
        self,
        repository: str,
        title: str,
        body: str,
        source_pr_id: PullRequestId,
        source_item_id: str,
    ) -> Issue:
        self.create_calls.append(
            (repository, title, body, source_pr_id, source_item_id)
        )
        return Issue(
            id=self._next_id,
            repository=repository,
            title=title,
            body=body,
            source_pr_id=source_pr_id,
            source_item_id=source_item_id,
        )


class TestCompositeIssueTracker:
    def test_create_routes_to_correct_platform(self):
        github_tracker = _StubIssueTracker(platform_id=100)
        forgejo_tracker = _StubIssueTracker(platform_id=200)
        composite = CompositeIssueTracker({
            "github": github_tracker,
            "forgejo": forgejo_tracker,
        })
        github_pr = PullRequestId(repository="github:owner/repo", number=7)
        forgejo_pr = PullRequestId(repository="codeberg:org/proj", number=8)

        gh_issue = composite.create(
            "github:owner/repo",
            "bug title",
            "bug body",
            source_pr_id=github_pr,
            source_item_id="gh-item",
        )
        fj_issue = composite.create(
            "codeberg:org/proj",
            "feat title",
            "feat body",
            source_pr_id=forgejo_pr,
            source_item_id="fj-item",
        )

        assert gh_issue.id == 100
        assert gh_issue.repository == "owner/repo"
        assert gh_issue.source_pr_id == github_pr
        assert fj_issue.id == 200
        assert fj_issue.repository == "org/proj"
        assert fj_issue.source_pr_id == forgejo_pr
        assert github_tracker.create_calls[0] == (
            "owner/repo",
            "bug title",
            "bug body",
            github_pr,
            "gh-item",
        )
        assert forgejo_tracker.create_calls[0] == (
            "org/proj",
            "feat title",
            "feat body",
            forgejo_pr,
            "fj-item",
        )

    def test_create_defaults_to_forgejo_without_prefix(self):
        forgejo_tracker = _StubIssueTracker(platform_id=300)
        composite = CompositeIssueTracker({"forgejo": forgejo_tracker})
        source_pr = PullRequestId(repository="owner/repo", number=9)

        issue = composite.create(
            "owner/repo",
            "title",
            "body",
            source_pr_id=source_pr,
            source_item_id="item-1",
        )

        assert issue.id == 300
        assert issue.repository == "owner/repo"
        assert issue.source_pr_id == source_pr
        assert forgejo_tracker.create_calls[0][0] == "owner/repo"

    def test_create_raises_for_unknown_platform(self):
        composite = CompositeIssueTracker({})
        source_pr = PullRequestId(repository="unknown:owner/repo", number=1)

        with pytest.raises(ValueError, match="No issue tracker for platform"):
            composite.create(
                "unknown:owner/repo",
                "title",
                "body",
                source_pr_id=source_pr,
                source_item_id="item-1",
            )
