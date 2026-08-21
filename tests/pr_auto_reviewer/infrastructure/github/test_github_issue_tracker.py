"""Behavioral tests for GithubIssueTracker."""

import pytest

from pr_auto_reviewer.domain.exceptions.issue_creation_error import (
    IssueCreationError,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.github.issue_tracker import (
    GithubIssueTracker,
)
from tests.fakes import FakeGitPlatformHttpClient


def _tracker(paths: dict) -> GithubIssueTracker:
    return GithubIssueTracker(FakeGitPlatformHttpClient(paths))


class TestGithubIssueTracker:
    """Exercises GithubIssueTracker.create across response shapes."""

    def test_create_when_success_then_returns_issue(self) -> None:
        """A successful POST yields a populated Issue."""
        tracker = _tracker({"/repos/o/r/issues": {"number": 7}})

        issue = tracker.create("o/r", "Title", "Body")

        assert issue.id == 7
        assert issue.repository == "o/r"
        assert issue.title == "Title"
        assert issue.body == "Body"

    def test_create_when_response_missing_number_then_uses_zero(self) -> None:
        """A response without a number defaults the issue id to zero."""
        tracker = _tracker({"/repos/o/r/issues": {}})

        issue = tracker.create("o/r", "Title", "Body")

        assert issue.id == 0

    def test_create_when_post_raises_then_raises_issue_creation_error(self) -> None:
        """A transport failure surfaces as IssueCreationError."""
        tracker = _tracker(
            {"/repos/o/r/issues": ConnectionError("down")}
        )

        with pytest.raises(IssueCreationError):
            tracker.create("o/r", "Title", "Body")

    def test_create_when_source_item_given_then_preserved(self) -> None:
        """The source item id is preserved on the returned Issue."""
        tracker = _tracker({"/repos/o/r/issues": {"number": 1}})

        issue = tracker.create("o/r", "T", "B", source_item_id="abc")

        assert issue.source_item_id == "abc"
        assert issue.source_pr_id == PullRequestId(repository="o/r", number=1)