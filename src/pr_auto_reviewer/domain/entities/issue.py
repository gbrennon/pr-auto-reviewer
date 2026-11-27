"""Issue — a tracker issue created from a review finding on the remote platform."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..exceptions import InvalidIssueBodyError
from ..value_objects.pull_request_id import PullRequestId


@dataclass(frozen=True)
class Issue:
    """A tracker issue created from a review finding on the remote platform.

    An issue has a platform-assigned numeric ID that persists.
    It can be updated, closed, or linked — it lives beyond the review cycle
    that created it.

    Immutable. "Mutation" methods return a new Issue.
    """

    id: int
    repository: str
    title: str
    body: str
    source_pr_id: PullRequestId
    source_item_id: str
    _is_closed: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(self.id, int)
            or isinstance(self.id, bool)
            or self.id <= 0
        ):
            raise ValueError("issue id must be a positive integer")
        if not isinstance(self.source_pr_id, PullRequestId):
            raise ValueError("source_pr_id must be a PullRequestId")
        if (
            not isinstance(self.source_item_id, str)
            or not self.source_item_id.strip()
        ):
            raise ValueError("source_item_id must be a non-empty string")


    def close(self) -> Issue:
        """Marks this issue as closed. Returns a new Issue."""
        return replace(self, _is_closed=True)

    def is_closed(self) -> bool:
        """Returns whether this issue is closed."""
        return self._is_closed

    def update_body(self, new_body: str) -> Issue:
        """Replaces the issue body with updated content. Returns a new Issue."""
        if not new_body or not isinstance(new_body, str):
            raise InvalidIssueBodyError("body must be a non-empty string")
        return replace(self, body=new_body)
