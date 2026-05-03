"""ChangesetFetcherPort — fetch PullRequestDiff for a given PR and SHA."""

from typing import Protocol

from ....domain.value_objects.pull_request_id import PullRequestId
from ....domain.value_objects.commit_sha import CommitSha
from ....domain.value_objects.pull_request_diff import PullRequestDiff


class ChangesetFetcherPort(Protocol):
    def fetch(self, pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff:
        ...
