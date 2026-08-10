"""ReviewPullRequestCommand — input for ReviewPullRequestService."""

from dataclasses import dataclass

from ...value_objects.pull_request_id import PullRequestId
from ...value_objects.commit_sha import CommitSha

@dataclass(frozen=True)
class ReviewPullRequestCommand:
    pr_id: PullRequestId
    head_sha: CommitSha
    title: str
    description: str = ""
    review_requested: bool = False
    force: bool = False
    target_branch: str = ""
