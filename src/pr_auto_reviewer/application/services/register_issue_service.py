"""RegisterIssueService — registers a single review item as a tracker issue."""

from __future__ import annotations

import logging

from ..commands.register_issue_command import RegisterIssueCommand
from ...domain.entities.review_item import ReviewItem
from ...domain.exceptions.pull_request_not_found_error import PullRequestNotFoundError
from ...domain.exceptions.review_item_not_found_error import ReviewItemNotFoundError
from ..ports.outbound.pull_request_repository import PullRequestRepository
from ..ports.outbound.review_reader_port import ReviewReaderPort
from ..ports.outbound.issue_tracker_port import IssueTrackerPort
from ..ports.inbound.register_issue_port import RegisterIssuePort
from ...domain.services.review_item_parser import ReviewItemParser
from ..serializers.issue_body_builder import IssueBodyBuilder

logger = logging.getLogger(__name__)

class RegisterIssueService(RegisterIssuePort):
    """Registers a single review item as a tracker issue on the remote platform.

    Triggered by a PR comment containing ``issue <short-id>``.
    The caller (adapter) is responsible for extracting the *issue_id* and
    building the ``RegisterIssueCommand`` from the comment.
    """

    def __init__(
        self,
        pr_repository: PullRequestRepository,
        review_reader: ReviewReaderPort,
        review_item_parser: ReviewItemParser,
        issue_tracker: IssueTrackerPort,
        issue_body_builder: IssueBodyBuilder,
    ) -> None:
        self._pr_repository = pr_repository
        self._review_reader = review_reader
        self._review_item_parser = review_item_parser
        self._issue_tracker = issue_tracker
        self._issue_body_builder = issue_body_builder

    def _find_item(self, items: list[ReviewItem], issue_id: str) -> ReviewItem:
        """Return the ReviewItem whose ``id`` (or fallback ``number``)
        matches *issue_id*.

        Raises:
            ReviewItemNotFoundError: when no item matches.
        """
        for item in items:
            if item.id == issue_id:
                return item

        try:
            id_ = int(issue_id)
        except ValueError:
            pass
        else:
            for item in items:
                if item.number == id_:
                    return item

        raise ReviewItemNotFoundError(
            f"review item '{issue_id}' not found in the latest review"
        )

    def execute(self, command: RegisterIssueCommand) -> None:
        logger.info(
            "Registering issue '%s' for PR %s (command: %r)",
            command.issue_id, command.pr_id, command.command_text,
        )

        pr = self._pr_repository.find(command.pr_id)
        if pr is None:
            raise PullRequestNotFoundError(
                f"PullRequest {command.pr_id} not found"
            )

        raw_body = self._review_reader.get_latest_review(pr.id)
        if not raw_body:
            raise ReviewItemNotFoundError(
                f"no review found for {command.pr_id}"
            )

        items = self._review_item_parser.parse(raw_body)
        if not items:
            raise ReviewItemNotFoundError(
                f"no review items found for {command.pr_id}"
            )

        item = self._find_item(items, command.issue_id)

        title, body = self._issue_body_builder.build(pr.id, item)
        self._issue_tracker.create(
            repository=pr.id.repository, title=title, body=body,
        )

        logger.info(
            "Issue '%s' registered for PR %s", command.issue_id, command.pr_id,
        )
