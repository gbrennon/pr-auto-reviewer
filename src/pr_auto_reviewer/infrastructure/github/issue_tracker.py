"""GithubIssueTracker — wraps GitPlatformHttpClient to implement IssueTrackerPort."""

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


class GithubIssueTracker(IssueTrackerPort):
    """Creates tracker issues on the remote platform."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    def create(
        self,
        repository: str,
        title: str,
        body: str,
        source_pr_id: PullRequestId,
        source_item_id: str,
    ) -> Issue:
        """POST a new issue to *repository* and return the Issue entity."""

        path = f"/repos/{repository}/issues"
        logger.debug(
            "Creating issue in %s: title='%s', body=%d chars",
            repository, title[:80], len(body),
        )
        try:
            response = self._client.post(
                path, {"title": title, "body": body}, repo=repository
            )
        except Exception as exc:
            raise IssueCreationError(
                repository=repository,
                item_number=source_pr_id.number,
                reason=str(exc),
            ) from exc

        issue_number = response.get("number") if isinstance(response, dict) else None
        if (
            not isinstance(issue_number, int)
            or isinstance(issue_number, bool)
            or issue_number <= 0
        ):
            raise IssueCreationError(
                repository=repository,
                item_number=source_pr_id.number,
                reason="response did not contain a positive integer number",
            )
        logger.debug("Issue created: %s #%d", repository, issue_number)
        return Issue(
            id=issue_number,
            repository=repository,
            title=title,
            body=body,
            source_pr_id=source_pr_id,
            source_item_id=source_item_id,
        )
