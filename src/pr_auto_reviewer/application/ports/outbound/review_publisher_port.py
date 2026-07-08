"""ReviewPublisherPort — publish a CodeReview verdict and body to a remote platform."""

from typing import Protocol

from ....domain.value_objects.pull_request_id import PullRequestId
from ....domain.value_objects.code_review import CodeReview

class ReviewPublisherPort(Protocol):
    def publish(self, pr_id: PullRequestId, review: CodeReview) -> None:
        ...
