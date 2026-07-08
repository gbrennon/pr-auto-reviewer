"""IssueTrackerPort — create a tracker issue on a remote platform."""

from typing import Protocol

from ....domain.entities.issue import Issue

class IssueTrackerPort(Protocol):
    def create(self, repository: str, title: str, body: str) -> Issue:
        ...
