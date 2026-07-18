"""CompositeCommentPublisher — dispatches comment-publishing by platform prefix."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.comment_publisher_port import (
    CommentPublisherPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from ._parse_platform_prefix import split_repository_prefix


class CompositeCommentPublisher(CommentPublisherPort):
    """Strips the platform prefix from *pr_id.repository* and delegates
    to the correct platform-specific ``CommentPublisherPort``."""

    def __init__(self, publishers: dict[str, CommentPublisherPort]) -> None:
        self._publishers = publishers

    def post(self, pr_id: PullRequestId, body: str) -> None:
        platform, clean_repo = split_repository_prefix(pr_id.repository)
        publisher = self._publishers.get(platform)
        if publisher is None:
            raise ValueError(
                f"No comment publisher for platform: {platform}"
            )
        clean_pr_id = PullRequestId(
            repository=clean_repo, number=pr_id.number,
        )
        publisher.post(clean_pr_id, body)
