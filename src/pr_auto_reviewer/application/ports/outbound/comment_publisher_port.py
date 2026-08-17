"""CommentPublisherPort — post a reply comment on a PR."""

from typing import Protocol

from ....domain.value_objects.pull_request_id import PullRequestId


class CommentPublisherPort(Protocol):
    def post(self, pr_id: PullRequestId, body: str) -> None:
        ...
