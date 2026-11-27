"""CompositeIssueTracker — dispatches issue-creation by platform prefix."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.issue_tracker_port import (
    IssueTrackerPort,
)
from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId

from ._parse_platform_prefix import split_repository_prefix


class CompositeIssueTracker(IssueTrackerPort):
    """Strips the platform prefix from *repository* and delegates to the
    correct platform-specific ``IssueTrackerPort``.

    Unlike other composites whose first argument is a ``PullRequestId``,
    ``IssueTrackerPort.create()`` takes a raw ``repository: str``."""

    def __init__(self, trackers: dict[str, IssueTrackerPort]) -> None:
        self._trackers = trackers

    def create(
        self,
        repository: str,
        title: str,
        body: str,
        source_pr_id: PullRequestId,
        source_item_id: str,
    ) -> Issue:
        platform, clean_repo = split_repository_prefix(repository)
        tracker = self._trackers.get(platform)
        if tracker is None:
            raise ValueError(f"No issue tracker for platform: {platform}")
        return tracker.create(
            clean_repo,
            title,
            body,
            source_pr_id=source_pr_id,
            source_item_id=source_item_id,
        )
