"""Fake pull request repository for tests."""

from pr_auto_reviewer.domain.entities.pull_request import PullRequest
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class FakePullRequestRepository:
    """Controlled PR persistence: returns a fixed PR and records calls."""

    def __init__(self, initial: PullRequest | None = None) -> None:
        self._pr = initial
        self.find_calls: list[PullRequestId] = []
        self.save_calls: list[PullRequest] = []
        self.reset_calls: int = 0

    def find(self, pr_id: PullRequestId) -> PullRequest | None:
        self.find_calls.append(pr_id)
        return self._pr

    def save(self, pr: PullRequest) -> None:
        self.save_calls.append(pr)
        self._pr = pr

    def reset(self) -> None:
        self.reset_calls += 1
        self._pr = None