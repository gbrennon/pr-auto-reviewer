"""ProcessIssueCommandsService — scans PR comments for issue-creation commands."""

from __future__ import annotations

from ...domain.entities.issue import Issue
from ...domain.entities.pull_request import PullRequest
from ...domain.entities.review_item import ReviewItem
from ...domain.exceptions import (
    IssueCreationError,
    PullRequestNotFoundError,
)
from ...domain.services.issue_command_parser import IssueCommandParser
from ...domain.services.review_item_parser import ReviewItemParser
from pr_auto_reviewer.domain.messages.commands.process_issue_commands_command import ProcessIssueCommandsCommand
from pr_auto_reviewer.domain.messages.messages import invalid_items_message, issues_created_message
from ..ports.inbound.process_issue_commands_use_case import ProcessIssueCommandsUseCase
from ..ports.outbound.comment_publisher_port import CommentPublisherPort
from ..ports.outbound.comment_reader_port import CommentReaderPort
from ..ports.outbound.issue_tracker_port import IssueTrackerPort
from ..ports.outbound.pull_request_repository import PullRequestRepository
from ..ports.outbound.review_reader_port import ReviewReaderPort
from ..serializers.issue_body_builder import IssueBodyBuilder


class ProcessIssueCommandsService(ProcessIssueCommandsUseCase):

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
        pr = self._load_pull_request(command)
        self._process_comments_for_pull_request(pr)

    def _load_pull_request(
        self, command: ProcessIssueCommandsCommand,
    ) -> PullRequest:
        pr = self._pr_repository.find(command.pr_id)

        if pr is None:
            raise PullRequestNotFoundError(
                f"PullRequest {command.pr_id} not found"
            )
        return pr

    def _fetch_latest_review_body(self, pr: PullRequest) -> str | None:
        return self._review_reader.get_latest_review(pr.id)

    def _parse_review_items(self, raw_body: str) -> list[ReviewItem]:
        return self._review_item_parser.parse(raw_body)

    def _fetch_comments(self, pr: PullRequest):
        return self._comment_reader.get_comments(pr.id)

    def _partition_item_numbers(
        self, requested: list[int], items: list[ReviewItem],
    ) -> tuple[list[int], list[int]]:
        valid_numbers = {item.number for item in items}
        valid: list[int] = []
        invalid: list[int] = []

        for n in requested:
            (valid if n in valid_numbers else invalid).append(n)

        return valid, invalid

    def _publish_invalid_items_message(
        self, pr: PullRequest, invalid: list[int],
        review_items: list[ReviewItem],
    ) -> None:
        self._comment_publisher.post(
            pr.id, invalid_items_message(invalid, review_items),
        )

    def _create_issues_for_valid_items(
        self, pr: PullRequest, valid: list[int],
        review_items: list[ReviewItem],
    ) -> list[Issue]:
        created: list[Issue] = []
        items_by_number = {item.number: item for item in review_items}

        for item_number in valid:
            item = items_by_number[item_number]
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
        return created

    def _publish_issues_created_message(
        self, pr: PullRequest, created_issues: list[Issue],
    ) -> None:
        self._comment_publisher.post(
            pr.id, issues_created_message(created_issues),
        )

    def _process_each_comment(
        self, pr: PullRequest, comments, review_items: list[ReviewItem],
    ) -> PullRequest:
        for comment in comments:
            if pr.is_comment_processed(comment.id):
                continue

            cmd = self._issue_command_parser.parse(
                comment.id.value, comment.body,
            )
            if cmd is None:
                continue

            pr = pr.mark_comment_processed(comment.id)
            valid, invalid = self._partition_item_numbers(
                cmd.item_numbers, review_items,
            )
            if invalid:
                self._publish_invalid_items_message(pr, invalid, review_items)
                continue

            created_issues = self._create_issues_for_valid_items(
                pr, valid, review_items,
            )

            if created_issues:
                self._publish_issues_created_message(pr, created_issues)
        return pr

    def _persist_pull_request(self, pr: PullRequest) -> None:
        self._pr_repository.save(pr)

    def _process_comments_for_pull_request(self, pr: PullRequest) -> None:
        raw_body = self._fetch_latest_review_body(pr)

        if not raw_body:
            return

        review_items = self._parse_review_items(raw_body)

        if not review_items:
            return

        comments = self._fetch_comments(pr)

        if not comments:
            return

        pr = self._process_each_comment(pr, comments, review_items)
        self._persist_pull_request(pr)
