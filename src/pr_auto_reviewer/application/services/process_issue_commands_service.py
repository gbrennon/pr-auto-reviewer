"""ProcessIssueCommandsService — scans PR comments for issue-creation commands."""

from __future__ import annotations

from collections.abc import Sequence

from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.entities.pull_request import PullRequest
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions import PullRequestNotFoundError
from pr_auto_reviewer.domain.messages.commands.process_issue_commands_command import (
    ProcessIssueCommandsCommand,
)
from pr_auto_reviewer.domain.messages.commands.register_issue_command import (
    RegisterIssueCommand,
)
from pr_auto_reviewer.domain.messages.messages import (
    invalid_items_message,
    issues_created_message,
)
from pr_auto_reviewer.domain.services.issue_command_parser import (
    IssueCommandParser,
)
from pr_auto_reviewer.domain.value_objects.pr_comment import PrComment

from ..ports.inbound.process_issue_commands_port import (
    ProcessIssueCommandsPort,
)
from ..ports.outbound.command_bus_port import CommandBusPort
from ..ports.outbound.comment_publisher_port import CommentPublisherPort
from ..ports.outbound.comment_reader_port import CommentReaderPort
from ..ports.outbound.pull_request_repository_port import (
    PullRequestRepositoryPort,
)


class ProcessIssueCommandsService(ProcessIssueCommandsPort):
    """Processes issue commands from PR comments by verifying and dispatching."""

    def __init__(
        self,
        pr_repository: PullRequestRepositoryPort,
        comment_reader: CommentReaderPort,
        comment_publisher: CommentPublisherPort,
        issue_command_parser: IssueCommandParser,
        command_bus: CommandBusPort,
    ) -> None:
        self._pr_repository = pr_repository
        self._comment_reader = comment_reader
        self._comment_publisher = comment_publisher
        self._issue_command_parser = issue_command_parser
        self._command_bus = command_bus

    def execute(self, command: ProcessIssueCommandsCommand) -> None:
        """Scan comments for issue commands and dispatch them."""
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

    def _fetch_comments(self, pr: PullRequest) -> list[PrComment]:
        return self._comment_reader.get_comments(pr.id)

    def _partition_item_ids(
        self, requested: list[str], items: Sequence[ReviewItem],
    ) -> tuple[list[str], list[str]]:
        valid_ids = {item.id for item in items}
        valid: list[str] = []
        invalid: list[str] = []

        for id_ in requested:
            (valid if id_ in valid_ids else invalid).append(id_)

        return valid, invalid

    def _publish_invalid_items_message(
        self,
        pr: PullRequest,
        invalid: list[str],
        review_items: Sequence[ReviewItem],
    ) -> None:
        self._comment_publisher.post(
            pr.id, invalid_items_message(invalid, list(review_items)),
        )

    def _dispatch_issue_creations(
        self, pr: PullRequest, valid: list[str]
    ) -> list[Issue]:
        created: list[Issue] = []
        for issue_id in valid:
            command = RegisterIssueCommand(pr_id=pr.id, issue_id=issue_id)
            result = self._command_bus.dispatch(command)
            if isinstance(result, Issue):
                created.append(result)
        return created

    def _publish_issues_created_message(
        self, pr: PullRequest, created_issues: list[Issue],
    ) -> None:
        self._comment_publisher.post(
            pr.id, issues_created_message(created_issues),
        )

    def _process_each_comment(
        self,
        pr: PullRequest,
        comments: list[PrComment],
        review_items: Sequence[ReviewItem],
    ) -> PullRequest:
        for comment in comments:
            pr = self._handle_single_comment(pr, comment, review_items)
        return pr

    def _handle_single_comment(
        self,
        pr: PullRequest,
        comment: PrComment,
        review_items: Sequence[ReviewItem],
    ) -> PullRequest:
        if pr.is_comment_processed(comment.id):
            return pr

        cmd = self._issue_command_parser.parse(
            comment.id.value, comment.body,
        )
        if cmd is None:
            return pr

        updated_pr = pr.mark_comment_processed(comment.id)
        valid, invalid = self._partition_item_ids(
            cmd.item_ids, review_items,
        )
        if invalid:
            self._publish_invalid_items_message(updated_pr, invalid, review_items)
            return updated_pr

        created_issues = self._dispatch_issue_creations(updated_pr, valid)
        if created_issues:
            self._publish_issues_created_message(updated_pr, created_issues)
        return updated_pr

    def _persist_pull_request(self, pr: PullRequest) -> None:
        self._pr_repository.save(pr)

    def _process_comments_for_pull_request(self, pr: PullRequest) -> None:
        items = pr.latest_review_items()
        if not items:
            return

        comments = self._fetch_comments(pr)
        if not comments:
            return

        pr = self._process_each_comment(pr, comments, items)
        self._persist_pull_request(pr)
