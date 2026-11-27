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

_SOURCE_PR = PullRequestId(repository="o/r", number=42)


def _tracker(paths: dict) -> GithubIssueTracker:
    return GithubIssueTracker(FakeGitPlatformHttpClient(paths))


class TestGithubIssueTracker:
    def test_create_when_success_then_returns_issue(self) -> None:
        tracker = _tracker({"/repos/o/r/issues": {"number": 7}})

        issue = tracker.create(
            "o/r",
            "Title",
            "Body",
            source_pr_id=_SOURCE_PR,
            source_item_id="item-1",
        )

        assert issue.id == 7
        assert issue.repository == "o/r"
        assert issue.title == "Title"
        assert issue.body == "Body"
        assert issue.source_pr_id == _SOURCE_PR
        assert issue.source_item_id == "item-1"

    def test_create_when_response_missing_number_then_raises(self) -> None:
        tracker = _tracker({"/repos/o/r/issues": {}})

        with pytest.raises(IssueCreationError):
            tracker.create(
                "o/r",
                "Title",
                "Body",
                source_pr_id=_SOURCE_PR,
                source_item_id="item-1",
            )

    @pytest.mark.parametrize("number", (None, "7", 0, -1, True))
    def test_create_when_number_is_not_positive_integer_then_raises(
        self, number: object
    ) -> None:
        tracker = _tracker({"/repos/o/r/issues": {"number": number}})

        with pytest.raises(IssueCreationError):
            tracker.create(
                "o/r",
                "Title",
                "Body",
                source_pr_id=_SOURCE_PR,
                source_item_id="item-1",
            )

    def test_create_when_post_raises_then_raises_issue_creation_error(self) -> None:
        tracker = _tracker(
            {"/repos/o/r/issues": ConnectionError("down")}
        )

        with pytest.raises(IssueCreationError):
            tracker.create(
                "o/r",
                "Title",
                "Body",
                source_pr_id=_SOURCE_PR,
                source_item_id="item-1",
            )