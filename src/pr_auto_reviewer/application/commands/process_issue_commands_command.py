"""ProcessIssueCommandsCommand — input for ProcessIssueCommandsService."""

from dataclasses import dataclass

from ...domain.value_objects.pull_request_id import PullRequestId
from ...domain.value_objects.commit_sha import CommitSha


@dataclass(frozen=True)
class ProcessIssueCommandsCommand:
    pr_id: PullRequestId
    head_sha: CommitSha
