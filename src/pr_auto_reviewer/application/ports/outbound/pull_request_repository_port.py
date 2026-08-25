"""PullRequestRepository — persistence port for the PullRequest aggregate."""

from __future__ import annotations

from typing import Protocol

from ....domain.entities.pull_request import PullRequest
from ....domain.value_objects.pull_request_id import PullRequestId


class PullRequestRepository(Protocol):
    def find(self, pr_id: PullRequestId) -> PullRequest | None:
        ...

    def save(self, pr: PullRequest) -> None:
        ...

    def reset(self) -> None:
        """Clear all persisted state (all reviewed PR records)."""
        ...
