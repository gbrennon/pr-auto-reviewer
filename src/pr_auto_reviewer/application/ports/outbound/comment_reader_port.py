"""CommentReaderPort — fetch comments posted on a PR."""

from typing import Protocol

from ....domain.value_objects.pr_comment import PrComment
from ....domain.value_objects.pull_request_id import PullRequestId


class CommentReaderPort(Protocol):
    def get_comments(self, pr_id: PullRequestId) -> list[PrComment]:
        ...
