"""ProcessIssueCommandsService — scans PR comments for issue-creation commands."""

from __future__ import annotations

from ..commands.process_issue_commands_command import ProcessIssueCommandsCommand
from ...domain.entities.pull_request import PullRequest
from ...domain.entities.issue import Issue
from ...domain.entities.review_item import ReviewItem
from ...domain.exceptions import (
    PullRequestNotFoundError,
    IssueCreationError,
)
from ..ports.outbound.pull_request_repository import PullRequestRepository
from ..ports.outbound.review_reader_port import ReviewReaderPort
from ..ports.outbound.comment_reader_port import CommentReaderPort
from ..ports.outbound.comment_publisher_port import CommentPublisherPort
from ..ports.outbound.issue_tracker_port import IssueTrackerPort
from ..ports.inbound.process_issue_commands_use_case import ProcessIssueCommandsUseCase
from ...domain.services.review_item_parser import ReviewItemParser
from ...domain.services.issue_command_parser import IssueCommandParser
from ..serializers.issue_body_builder import IssueBodyBuilder
from ..messages.messages import invalid_items_message, issues_created_message


class ProcessIssueCommandsService(ProcessIssueCommandsUseCase):
    """Scans new PR comments for issue-creation commands, validates
    requested item numbers, and creates tracker issues.
    """

    def __init__(
        self,
        pr_repository: PullRequestRepository,
        review_reader: ReviewReaderPort,
        comment_reader: CommentReaderPort,
        comment_publisher: CommentPublisherPort,
        issue_tracker: IssueTrackerPort,
        review_item_parser: ReviewItemParser,
        issue_command_parser: IssueCommandParser,
        issue_body_builder: IssueBodyBuilder,
    ) -> None:
        self._pr_repository = pr_repository
        self._review_reader = review_reader
        self._comment_reader = comment_reader
        self._comment_publisher = comment_publisher
        self._issue_tracker = issue_tracker
        self._review_item_parser = review_item_parser
        self._issue_command_parser = issue_command_parser
        self._issue_body_builder = issue_body_builder

    def execute(self, command: ProcessIssueCommandsCommand) -> None:
        pr = self._pr_repository.find(command.pr_id)
        if pr is None:
            raise PullRequestNotFoundError(
                f"PullRequest {command.pr_id} not found"
            )
        self._run(pr)

    # ─── private ────────────────────────────────────────────────

    def _run(self, pr: PullRequest) -> None:
        # 2. Fetch latest review body
        raw_body = self._review_reader.get_latest_review(pr.id)
        if not raw_body:
            return

        # 3. Parse review items
        review_items = self._review_item_parser.parse(raw_body)
        if not review_items:
            return

        # 4. Fetch comments
        comments = self._comment_reader.get_comments(pr.id)
        if not comments:
            return

        # 5. Process each comment
        for comment in comments:
            if pr.is_comment_processed(comment.id):
                continue

            cmd = self._issue_command_parser.parse(
                comment.id.value, comment.body
            )
            if cmd is None:
                continue

            pr = pr.mark_comment_processed(comment.id)

            valid, invalid = _partition_numbers(
                cmd.item_numbers, review_items
            )

            if invalid:
                self._comment_publisher.post(
                    pr.id,
                    invalid_items_message(invalid, review_items),
                )
                continue

            created: list[Issue] = []
            for item_number in valid:
                item = review_items[item_number - 1]
                title, body = self._issue_body_builder.build(pr.id, item)
                try:
                    issue = self._issue_tracker.create(
                        repository=pr.id.repository,
                        title=title,
                        body=body,
                    )
                    created.append(issue)
                except IssueCreationError:
                    raise

            if created:
                self._comment_publisher.post(
                    pr.id, issues_created_message(created),
                )

        # 6. Persist processed comment state
        self._pr_repository.save(pr)


def _partition_numbers(
    requested: list[int], items: list[ReviewItem],
) -> tuple[list[int], list[int]]:
    valid_numbers = {item.number for item in items}
    valid: list[int] = []
    invalid: list[int] = []
    for n in requested:
        (valid if n in valid_numbers else invalid).append(n)
    return valid, invalid
