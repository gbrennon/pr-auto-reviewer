"""CompositeReviewReader — dispatches review-reading by platform prefix."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.review_reader_port import (
    ReviewReaderPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from ._parse_platform_prefix import split_repository_prefix


class CompositeReviewReader(ReviewReaderPort):
    """Strips the platform prefix from *pr_id.repository* and delegates
    to the correct platform-specific ``ReviewReaderPort``."""

    def __init__(self, readers: dict[str, ReviewReaderPort]) -> None:
        self._readers = readers

    def get_latest_review(self, pr_id: PullRequestId) -> str | None:
        platform, clean_repo = split_repository_prefix(pr_id.repository)
        reader = self._readers.get(platform)
        if reader is None:
            raise ValueError(f"No review reader for platform: {platform}")
        clean_pr_id = PullRequestId(
            repository=clean_repo, number=pr_id.number,
        )
        return reader.get_latest_review(clean_pr_id)
