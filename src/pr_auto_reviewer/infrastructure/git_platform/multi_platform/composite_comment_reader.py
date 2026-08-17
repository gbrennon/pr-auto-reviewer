"""CompositeCommentReader — dispatches comment-reading by platform prefix."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.comment_reader_port import (
    CommentReaderPort,
)
from pr_auto_reviewer.domain.value_objects.pr_comment import PrComment
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId

from ._parse_platform_prefix import split_repository_prefix


class CompositeCommentReader(CommentReaderPort):
    """Strips the platform prefix from *pr_id.repository* and delegates
    to the correct platform-specific ``CommentReaderPort``."""

    def __init__(self, readers: dict[str, CommentReaderPort]) -> None:
        self._readers = readers

    def get_comments(self, pr_id: PullRequestId) -> list[PrComment]:
        platform, clean_repo = split_repository_prefix(pr_id.repository)
        reader = self._readers.get(platform)
        if reader is None:
            raise ValueError(f"No comment reader for platform: {platform}")
        clean_pr_id = PullRequestId(
            repository=clean_repo, number=pr_id.number,
        )
        return reader.get_comments(clean_pr_id)
