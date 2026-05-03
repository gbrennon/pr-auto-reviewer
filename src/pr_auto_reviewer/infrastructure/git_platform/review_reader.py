"""GitReviewReaderAdapter — wraps GitPlatformHttpClient to implement ReviewReaderPort."""

from __future__ import annotations

import logging

from pr_auto_reviewer.application.ports.outbound.review_reader_port import (
    ReviewReaderPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)

logger = logging.getLogger(__name__)


class GitReviewReaderAdapter(ReviewReaderPort):
    """Reads the most recently submitted PR review body."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    # ------------------------------------------------------------------ [port]
    def get_latest_review(self, pr_id: PullRequestId) -> str | None:
        """Return the body string of the most recent review, or None."""

        # -- [http] GET reviews list -----------------------------------------
        path = f"/repos/{pr_id.repository}/pulls/{pr_id.number}/reviews"
        reviews = self._client.get(path, limit=10)

        # -- [map] sort by submitted_at descending, pick first ---------------
        if isinstance(reviews, list):
            sorted_reviews = sorted(
                reviews,
                key=lambda r: r.get("submitted_at", ""),
                reverse=True,
            )
            if sorted_reviews:
                body: str | None = sorted_reviews[0].get("body")
                return body
        elif isinstance(reviews, dict) and reviews:
            # Some platforms return a single object.
            return reviews.get("body")

        return None
