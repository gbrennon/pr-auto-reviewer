"""Fake changeset fetcher for tests."""

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class FakeChangesetFetcher:
    """Returns a fixed PullRequestDiff, tracks call count."""

    def __init__(self, diff: PullRequestDiff) -> None:
        self._diff = diff
        self.fetch_calls: list[tuple[PullRequestId, CommitSha]] = []

    def fetch(self, pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff:
        self.fetch_calls.append((pr_id, sha))
        return self._diff