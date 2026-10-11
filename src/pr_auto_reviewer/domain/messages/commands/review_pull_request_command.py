"""ReviewPullRequestCommand — input for ReviewPullRequestService."""

from dataclasses import dataclass

from ...value_objects.commit_sha import CommitSha
from ...value_objects.pull_request_id import PullRequestId


@dataclass(frozen=True)
class ReviewPullRequestCommand:
    pr_id: PullRequestId
    head_sha: CommitSha
    title: str
    description: str = ""
    review_requested: bool = False
    force: bool = False
    target_branch: str = ""
    review_request_event_id: int | None = None
    latest_review_id: int | None = None
    latest_review_dismissed: bool = False
