"""ForgejoIssueTracker — wraps GitPlatformHttpClient to implement IssueTrackerPort."""

from __future__ import annotations

import logging

from pr_auto_reviewer.application.ports.outbound.issue_tracker_port import (
    IssueTrackerPort,
)
from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.exceptions.issue_creation_error import (
    IssueCreationError,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)

logger = logging.getLogger(__name__)

class ForgejoIssueTracker(IssueTrackerPort):
    """Creates tracker issues on the remote platform."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    def create(self, repository: str, title: str, body: str) -> Issue:
        """POST a new issue to *repository* and return the Issue entity."""

        path = f"/repos/{repository}/issues"
        logger.debug(
            "Creating issue in %s: title='%s', body=%d chars",
            repository, title[:80], len(body),
        )
        try:
            response = self._client.post(path, {"title": title, "body": body})
        except Exception as exc:
            raise IssueCreationError(
                repository=repository,
                item_number=0,
                reason=str(exc),
            ) from exc

        issue_number = int(response.get("number", 0))
        logger.debug("Issue created: %s #%d", repository, issue_number)
        return Issue(
            id=issue_number,
            repository=repository,
            title=title,
            body=body,
            source_pr_id=PullRequestId(repository=repository, number=1),
            source_item_number=0,
        )
