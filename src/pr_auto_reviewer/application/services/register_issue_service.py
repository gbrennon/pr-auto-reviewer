"""RegisterIssueService — registers a single review item as a tracker issue."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from pr_auto_reviewer.application.ports.inbound.prepare_issue_content_port import (
    PrepareIssueContentPort,
)
from pr_auto_reviewer.application.ports.inbound.register_issue_port import (
    RegisterIssuePort,
)
from pr_auto_reviewer.application.ports.outbound.issue_tracker_port import (
    IssueTrackerPort,
)
from pr_auto_reviewer.application.ports.outbound.pull_request_repository_port import (
    PullRequestRepositoryPort,
)
from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions.pull_request_not_found_error import (
    PullRequestNotFoundError,
)
from pr_auto_reviewer.domain.exceptions.review_item_not_found_error import (
    ReviewItemNotFoundError,
)
from pr_auto_reviewer.domain.messages.commands.prepare_issue_content_command import (
    PrepareIssueContentCommand,
)
from pr_auto_reviewer.domain.messages.commands.register_issue_command import (
    RegisterIssueCommand,
)

logger = logging.getLogger(__name__)


class RegisterIssueService(RegisterIssuePort):
    """Registers a single review item as a tracker issue on the remote platform."""

    def __init__(
        self,
        pr_repository: PullRequestRepositoryPort,
        issue_content_preparer: PrepareIssueContentPort,
        issue_tracker: IssueTrackerPort,
    ) -> None:
        self._pr_repository = pr_repository
        self._issue_content_preparer = issue_content_preparer
        self._issue_tracker = issue_tracker

    def execute(self, command: RegisterIssueCommand) -> Issue:
        """Register the review item identified by command as an issue and return it."""
        logger.info(
            "Registering issue '%s' for PR %s",
            command.issue_id,
            command.pr_id,
        )

        pr = self._pr_repository.find(command.pr_id)
        if pr is None:
            raise PullRequestNotFoundError(
                f"PullRequest {command.pr_id} not found"
            )

        items = pr.latest_review_items()
        item = self._find_item(items, command.issue_id)
        content = self._issue_content_preparer.execute(
            PrepareIssueContentCommand(pr_id=pr.id, item=item)
        )

        created_issue = self._issue_tracker.create(
            repository=pr.id.repository,
            title=content.title,
            body=content.body,
            source_item_id=item.id,
        )

        logger.info(
            "Issue '%s' registered for PR %s as issue #%s",
            command.issue_id,
            command.pr_id,
            created_issue.id,
        )
        return created_issue

    @staticmethod
    def _find_item(items: Sequence[ReviewItem], issue_id: str) -> ReviewItem:
        for item in items:
            if item.id == issue_id:
                return item

        raise ReviewItemNotFoundError(
            f"review item '{issue_id}' not found in the latest review"
        )
