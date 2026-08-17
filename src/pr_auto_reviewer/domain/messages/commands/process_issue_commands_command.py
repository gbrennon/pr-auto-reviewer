"""ProcessIssueCommandsCommand — input for ProcessIssueCommandsService."""

from dataclasses import dataclass

from ...value_objects.commit_sha import CommitSha
from ...value_objects.pull_request_id import PullRequestId


@dataclass(frozen=True)
class ProcessIssueCommandsCommand:
    pr_id: PullRequestId
    head_sha: CommitSha
