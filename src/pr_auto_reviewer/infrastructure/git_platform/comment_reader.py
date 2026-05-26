"""GitCommentReaderAdapter — wraps GitPlatformHttpClient to implement CommentReaderPort."""

from __future__ import annotations

import logging
from datetime import datetime

from pr_auto_reviewer.application.ports.outbound.comment_reader_port import (
    CommentReaderPort,
)
from pr_auto_reviewer.domain.value_objects.comment_id import CommentId
from pr_auto_reviewer.domain.value_objects.pr_comment import PrComment
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)

logger = logging.getLogger(__name__)


class GitCommentReaderAdapter(CommentReaderPort):
    """Fetches PR comments and maps them to domain PrComment objects."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    # ------------------------------------------------------------------ [port]
    def get_comments(self, pr_id: PullRequestId) -> list[PrComment]:
        """Return all comments on *pr_id*, sorted by creation date ascending."""

        # -- [http] GET comments ---------------------------------------------
        path = f"/repos/{pr_id.repository}/issues/{pr_id.number}/comments"
        logger.info("Fetching comments for %s", pr_id)
        raw_comments = self._client.get(path, limit=50)

        # Normalise to list — some platforms wrap in a dict under "data".
        if isinstance(raw_comments, dict):
            entries: list[dict] = raw_comments.get("data", raw_comments.get("comments", []))
            if not isinstance(entries, list):
                entries = [raw_comments] if raw_comments else []
        elif isinstance(raw_comments, list):
            entries = raw_comments
        else:
            entries = []

        # -- [map] build PrComment objects -----------------------------------
        comments: list[PrComment] = []
        logger.debug("Found %d raw comment entries for %s", len(entries), pr_id)
        for entry in entries:
            body = entry.get("body", "")
            created_str = entry.get("created_at", "")
            try:
                created_at = datetime.fromisoformat(
                    created_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                created_at = datetime.min

            comments.append(
                PrComment(
                    id=CommentId(str(entry.get("id", ""))),
                    body=body,
                    created_at=created_at,
                )
            )

        # -- [map] sort by created_at ascending, return ----------------------
        comments.sort(key=lambda c: c.created_at)
        logger.debug("Returning %d comments for %s", len(comments), pr_id)
        logger.info("GitCommentReaderAdapter return: %d comments for %s", len(comments), pr_id)
        return comments
