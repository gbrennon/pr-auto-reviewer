"""NullPullRequestRepository — no-op persistence for terminal-only mode."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.pull_request_repository import (
    PullRequestRepository,
)
from pr_auto_reviewer.domain.entities.pull_request import PullRequest
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class NullPullRequestRepository(PullRequestRepository):
    """Discards all state.  find() always returns None, save() is a no-op.

    Used when output_mode is "terminal" so that review state is never
    persisted across runs.
    """

    def find(self, pr_id: PullRequestId) -> PullRequest | None:
        return None

    def save(self, pr: PullRequest) -> None:
        pass

    def reset(self) -> None:
        pass
