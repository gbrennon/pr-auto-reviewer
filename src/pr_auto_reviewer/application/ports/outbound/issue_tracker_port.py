"""IssueTrackerPort — create a tracker issue on a remote platform."""

from typing import Protocol

from ....domain.entities.issue import Issue
from ....domain.value_objects.pull_request_id import PullRequestId

class IssueTrackerPort(Protocol):
    def create(
        self,
        repository: str,
        title: str,
        body: str,
        source_pr_id: PullRequestId,
        source_item_id: str,
    ) -> Issue:
        ...
