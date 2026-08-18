"""GithubReviewReader — wraps GitPlatformHttpClient to implement ReviewReaderPort."""

from __future__ import annotations

import logging
from typing import Any, cast

from pr_auto_reviewer.application.ports.outbound.review_reader_port import (
    ReviewReaderPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)

logger = logging.getLogger(__name__)

class GithubReviewReader(ReviewReaderPort):
    """Reads the most recently submitted PR review body."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    def get_latest_review(self, pr_id: PullRequestId) -> str | None:
        """Return the body string of the most recent review, or None."""

        path = f"/repos/{pr_id.repository}/pulls/{pr_id.number}/reviews"
        logger.info("Fetching latest review for %s", pr_id)
        reviews_response = self._client.get(path, limit=10, repo=pr_id.repository)
        reviews = cast("list[dict[str, Any]] | dict[str, Any]", reviews_response)

        if isinstance(reviews, list):
            sorted_reviews = sorted(
                reviews,
                key=lambda r: r.get("submitted_at", ""),
                reverse=True,
            )
            if sorted_reviews:
                body: str | None = sorted_reviews[0].get("body")
                logger.debug(
                    "Latest review body: %s chars", len(body) if body else 0,
                )
                logger.info("GithubReviewReader return: body=%s chars", len(body) if body else 0)
                return body
            logger.debug("No reviews found for %s", pr_id)
        elif isinstance(reviews, dict) and reviews:
            body = reviews.get("body")
            logger.debug(
                "Single review object, body: %s chars", len(body) if body else 0,
            )
            logger.info("GithubReviewReader return: body=%s chars", len(body) if body else 0)
            return body

        logger.info("No review available for %s", pr_id)
        return None
