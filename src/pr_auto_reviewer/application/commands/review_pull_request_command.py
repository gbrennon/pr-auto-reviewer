"""ReviewPullRequestCommand — input for ReviewPullRequestService."""

from dataclasses import dataclass

from ...domain.value_objects.pull_request_id import PullRequestId
from ...domain.value_objects.commit_sha import CommitSha

@dataclass(frozen=True)
class ReviewPullRequestCommand:
    pr_id: PullRequestId
    head_sha: CommitSha
    title: str
    description: str = ""
    updated_at: str | None = None
    force: bool = False
    target_branch: str = ""
