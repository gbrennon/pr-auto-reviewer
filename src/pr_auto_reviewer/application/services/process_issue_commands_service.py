"""ProcessIssueCommandsService — scans PR comments for review commands."""

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
    dismissed_items_message,
    invalid_items_message,
    issues_created_message,
    rejected_command_items_message,
)
from pr_auto_reviewer.domain.services.issue_command_parser import (
    IssueCommandParser,
)
from pr_auto_reviewer.domain.value_objects.issue_command_action import (
    IssueCommandAction,
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
        self, requested: Sequence[str], items: Sequence[ReviewItem],
    ) -> tuple[list[str], list[str], list[str]]:
        items_by_id = {item.id: item for item in items}
        valid: list[str] = []
        rejected: list[str] = []
        unknown: list[str] = []

        for item_id in requested:
            item = items_by_id.get(item_id)
            if item is None:
                unknown.append(item_id)
            elif item.is_open and not item.is_blocking:
                valid.append(item_id)
            else:
                rejected.append(item_id)

        return valid, rejected, unknown

    def _publish_invalid_items_message(
        self,
        pr: PullRequest,
        invalid: list[str],
        review_items: Sequence[ReviewItem],
    ) -> None:
        self._comment_publisher.post(
            pr.id, invalid_items_message(invalid, list(review_items)),
        )

    def _publish_rejected_items_message(
        self,
        pr: PullRequest,
        rejected: list[str],
        action: IssueCommandAction,
        review_items: Sequence[ReviewItem],
    ) -> None:
        self._comment_publisher.post(
            pr.id,
            rejected_command_items_message(action, rejected, review_items),
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
        self,
        pr: PullRequest,
        created_issues: list[Issue],
        review_items: Sequence[ReviewItem],
    ) -> None:
        self._comment_publisher.post(
            pr.id, issues_created_message(created_issues, review_items),
        )

    def _publish_dismissed_items_message(
        self,
        pr: PullRequest,
        dismissed: list[str],
        review_items: Sequence[ReviewItem],
    ) -> None:
        self._comment_publisher.post(
            pr.id, dismissed_items_message(dismissed, review_items),
        )

    def _process_each_comment(
        self,
        pr: PullRequest,
        comments: list[PrComment],
    ) -> PullRequest:
        for comment in comments:
            pr = self._handle_single_comment(
                pr, comment, pr.latest_review_items(),
            )
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
        valid, rejected, unknown = self._partition_item_ids(
            cmd.item_ids, review_items,
        )
        if unknown:
            self._publish_invalid_items_message(
                updated_pr, unknown, review_items,
            )
        if rejected:
            self._publish_rejected_items_message(
                updated_pr, rejected, cmd.action, review_items,
            )
        if unknown or rejected:
            return updated_pr

        if cmd.action is IssueCommandAction.DISMISS:
            updated_pr = updated_pr.dismiss_review_items(*valid)
            if valid:
                self._publish_dismissed_items_message(
                    updated_pr, valid, review_items,
                )
            return updated_pr

        available_ids = list(
            dict.fromkeys(
                item_id
                for item_id in valid
                if item_id not in updated_pr.created_issue_item_ids
            )
        )
        created_issues = self._dispatch_issue_creations(
            updated_pr, available_ids,
        )
        updated_pr = updated_pr.record_created_issue_items(
            *(issue.source_item_id for issue in created_issues)
        )
        if created_issues:
            self._publish_issues_created_message(
                updated_pr, created_issues, review_items,
            )
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

        pr = self._process_each_comment(pr, comments)
        self._persist_pull_request(pr)
