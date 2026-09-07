"""PrepareIssueContentCommand — input for preparing issue title and body."""

from dataclasses import dataclass

from ...entities.review_item import ReviewItem
from ...value_objects.pull_request_id import PullRequestId


@dataclass(frozen=True)
class PrepareIssueContentCommand:
    """Command to prepare issue title and markdown body for a review item."""

    pr_id: PullRequestId
    item: ReviewItem
