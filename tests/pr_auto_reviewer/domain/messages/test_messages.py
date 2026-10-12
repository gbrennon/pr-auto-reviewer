"""Tests for review-item status details in repository comments."""

from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.messages import (
    dismissed_items_message,
    issues_created_message,
    rejected_command_items_message,
)
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.issue_command_action import (
    IssueCommandAction,
)
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_item_status import ReviewItemStatus


class TestIssueCreatedMessage:
    """Repository comments identify the source item and its current status."""

    def test_open_blocking_item_is_reported_as_still_relevant(self) -> None:
        item = ReviewItem(
            id="afc64b",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="src/service.py",
            description="Handle the failure path",
        )
        issue = Issue(
            id=178,
            repository="gbrennon/ephact",
            title="Handle the failure path",
            body="Details",
            source_pr_id=PullRequestId(repository="gbrennon/ephact", number=177),
            source_item_id=item.id,
        )

        message = issues_created_message([issue], [item])

        assert "review item `afc64b`" in message
        assert "(major bug, blocking)" in message
        assert "status: open (still relevant)" in message

    def test_resolved_item_is_reported_as_no_longer_relevant(self) -> None:
        item = ReviewItem(
            id="fb864c",
            severity=ItemSeverity.INFO,
            category=IssueCategory.GENERAL,
            file_path="src/config.py",
            description="Clarify configuration construction",
            status=ReviewItemStatus.RESOLVED,
        )
        issue = Issue(
            id=179,
            repository="gbrennon/ephact",
            title="Clarify configuration construction",
            body="Details",
            source_pr_id=PullRequestId(repository="gbrennon/ephact", number=177),
            source_item_id=item.id,
        )

        message = issues_created_message([issue], [item])

        assert "review item `fb864c`" in message
        assert "(info general, non-blocking)" in message
        assert "status: resolved (no longer relevant)" in message

    def test_dismissed_message_identifies_item(self) -> None:
        """Dismissal acknowledgements identify the non-blocking item."""
        item = ReviewItem(
            id="s1",
            severity=ItemSeverity.INFO,
            category=IssueCategory.STYLE,
            file_path="src/config.py",
            description="Clarify configuration",
        )

        message = dismissed_items_message([item.id], [item])

        assert "Dismissed 1 non-blocking review item(s)" in message
        assert "`s1` (info style, non-blocking; status: open)" in message

    def test_rejected_message_identifies_blocking_item(self) -> None:
        """Rejection acknowledgements explain the blocking restriction."""
        item = ReviewItem(
            id="b1",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="src/service.py",
            description="Handle failure",
        )

        message = rejected_command_items_message(
            IssueCommandAction.CREATE_ISSUE, [item.id], [item],
        )

        assert "Cannot create tracker issues for:" in message
        assert "`b1` (major bug, blocking; status: open)" in message
