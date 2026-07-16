"""GithubCommentPublisher — wraps GitPlatformHttpClient to implement CommentPublisherPort."""

from __future__ import annotations

import logging

from pr_auto_reviewer.application.ports.outbound.comment_publisher_port import (
    CommentPublisherPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)

logger = logging.getLogger(__name__)

class GithubCommentPublisher(CommentPublisherPort):
    """Posts a reply comment on a PR; failure is non-fatal (logged only)."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    def post(self, pr_id: PullRequestId, body: str) -> None:
        """POST a comment on *pr_id*. Logs warning on failure; does not raise."""
        path = f"/repos/{pr_id.repository}/issues/{pr_id.number}/comments"
        logger.info(
            "Posting comment on %s: %d chars", pr_id, len(body),
        )

        try:
            response = self._client.post(path, {"body": body}, repo=pr_id.repository)
            logger.info("Comment posted on %s response=%s", pr_id, list(response.keys()) if isinstance(response, dict) else "ok")
        except Exception:
            logger.warning(
                "Failed to post comment on %s (non-fatal)", pr_id
            )
