"""TokenVerifierPort — verify token validity and write access before review."""

from typing import Protocol

from ....domain.value_objects.pull_request_id import PullRequestId


class TokenVerifierPort(Protocol):
    def can_review(self, pr_id: PullRequestId) -> bool:
        """Return whether all required API capabilities are available."""
        ...

    def verify(self, pr_id: PullRequestId) -> None:
        ...
