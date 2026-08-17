"""ReviewPublisherPort — publish a CodeReview verdict and body to a remote platform."""

from typing import Protocol

from ....domain.value_objects.code_review import CodeReview
from ....domain.value_objects.pull_request_diff import PullRequestDiff
from ....domain.value_objects.pull_request_id import PullRequestId


class ReviewPublisherPort(Protocol):
    def publish(self, pr_id: PullRequestId, review: CodeReview, diff: PullRequestDiff | None = None) -> None:
        ...
