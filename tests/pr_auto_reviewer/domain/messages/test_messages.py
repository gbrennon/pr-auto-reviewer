"""Tests for review-item status details in repository comments."""

from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.messages import issues_created_message
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


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
            status="resolved",
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
