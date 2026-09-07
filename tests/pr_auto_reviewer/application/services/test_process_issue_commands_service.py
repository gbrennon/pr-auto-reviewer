"""Application-layer tests for ProcessIssueCommandsService."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from pr_auto_reviewer.application.services.process_issue_commands_service import (
    ProcessIssueCommandsService,
)
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
from pr_auto_reviewer.domain.services.issue_command_parser import (
    IssueCommandParser,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.comment_id import CommentId
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pr_comment import PrComment
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)


class TestProcessIssueCommandsService:

    def test_processes_issue_command_and_dispatches_creations(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
        _pr_with_review: PullRequest,
        _item: ReviewItem,
    ) -> None:
        mock_pr_repository = MagicMock()
        mock_pr_repository.find.return_value = _pr_with_review

        mock_comment_reader = MagicMock()
        mock_comment_reader.get_comments.return_value = [
            PrComment(
                id=CommentId(value="c1"),
                body=f"create issue {_item.id}",
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
            )
        ]

        mock_comment_publisher = MagicMock()
        bus = InMemoryCommandBus()

        created_issue = Issue(
            id=101,
            repository="owner/repo",
            title="[MAJOR] bug: broken",
            body="body",
            source_pr_id=_pr_id,
            source_item_id=_item.id,
        )
        dispatched_commands: list[RegisterIssueCommand] = []

        def handle_register(command: RegisterIssueCommand) -> Issue:
            dispatched_commands.append(command)
            return created_issue

        bus.register(RegisterIssueCommand, handle_register)

        service = ProcessIssueCommandsService(
            pr_repository=mock_pr_repository,
            comment_reader=mock_comment_reader,
            comment_publisher=mock_comment_publisher,
            issue_command_parser=IssueCommandParser(),
            command_bus=bus,
        )

        service.execute(
            ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha)
        )

        assert len(dispatched_commands) == 1
        assert dispatched_commands[0].issue_id == _item.id
        mock_comment_publisher.post.assert_called_once()
        mock_pr_repository.save.assert_called_once()

    def test_skips_already_processed_comment(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
        _pr_with_review: PullRequest,
        _item: ReviewItem,
    ) -> None:
        processed_pr = _pr_with_review.mark_comment_processed(
            CommentId(value="c1")
        )
        mock_pr_repository = MagicMock()
        mock_pr_repository.find.return_value = processed_pr

        mock_comment_reader = MagicMock()
        mock_comment_reader.get_comments.return_value = [
            PrComment(
                id=CommentId(value="c1"),
                body=f"create issue {_item.id}",
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
            )
        ]

        mock_comment_publisher = MagicMock()
        bus = InMemoryCommandBus()

        service = ProcessIssueCommandsService(
            pr_repository=mock_pr_repository,
            comment_reader=mock_comment_reader,
            comment_publisher=mock_comment_publisher,
            issue_command_parser=IssueCommandParser(),
            command_bus=bus,
        )

        service.execute(
            ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha)
        )

        mock_comment_publisher.post.assert_not_called()

    def test_noop_when_no_review_items(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
    ) -> None:
        empty_pr = PullRequest(id=_pr_id, title="Test PR", head_sha=_sha)
        mock_pr_repository = MagicMock()
        mock_pr_repository.find.return_value = empty_pr

        mock_comment_reader = MagicMock()
        mock_comment_publisher = MagicMock()
        bus = InMemoryCommandBus()

        service = ProcessIssueCommandsService(
            pr_repository=mock_pr_repository,
            comment_reader=mock_comment_reader,
            comment_publisher=mock_comment_publisher,
            issue_command_parser=IssueCommandParser(),
            command_bus=bus,
        )

        service.execute(
            ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha)
        )

        mock_comment_reader.get_comments.assert_not_called()
        mock_comment_publisher.post.assert_not_called()

    def test_noop_when_no_comments(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
        _pr_with_review: PullRequest,
    ) -> None:
        mock_pr_repository = MagicMock()
        mock_pr_repository.find.return_value = _pr_with_review

        mock_comment_reader = MagicMock()
        mock_comment_reader.get_comments.return_value = []
        mock_comment_publisher = MagicMock()
        bus = InMemoryCommandBus()

        service = ProcessIssueCommandsService(
            pr_repository=mock_pr_repository,
            comment_reader=mock_comment_reader,
            comment_publisher=mock_comment_publisher,
            issue_command_parser=IssueCommandParser(),
            command_bus=bus,
        )

        service.execute(
            ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha)
        )

        mock_comment_publisher.post.assert_not_called()

    def test_raises_when_pr_not_found(
        self, _pr_id: PullRequestId, _sha: CommitSha
    ) -> None:
        mock_pr_repository = MagicMock()
        mock_pr_repository.find.return_value = None

        service = ProcessIssueCommandsService(
            pr_repository=mock_pr_repository,
            comment_reader=MagicMock(),
            comment_publisher=MagicMock(),
            issue_command_parser=IssueCommandParser(),
            command_bus=InMemoryCommandBus(),
        )

        with pytest.raises(PullRequestNotFoundError):
            service.execute(
                ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha)
            )

    def test_skips_non_command_comment(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
        _pr_with_review: PullRequest,
    ) -> None:
        mock_pr_repository = MagicMock()
        mock_pr_repository.find.return_value = _pr_with_review

        mock_comment_reader = MagicMock()
        mock_comment_reader.get_comments.return_value = [
            PrComment(
                id=CommentId(value="c2"),
                body="This is a regular discussion comment",
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
            )
        ]

        mock_comment_publisher = MagicMock()
        bus = InMemoryCommandBus()

        service = ProcessIssueCommandsService(
            pr_repository=mock_pr_repository,
            comment_reader=mock_comment_reader,
            comment_publisher=mock_comment_publisher,
            issue_command_parser=IssueCommandParser(),
            command_bus=bus,
        )

        service.execute(
            ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha)
        )

        mock_comment_publisher.post.assert_not_called()

    def test_publishes_invalid_items_message(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
        _pr_with_review: PullRequest,
    ) -> None:
        mock_pr_repository = MagicMock()
        mock_pr_repository.find.return_value = _pr_with_review

        mock_comment_reader = MagicMock()
        mock_comment_reader.get_comments.return_value = [
            PrComment(
                id=CommentId(value="c2"),
                body="create issue invalid-id",
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
            )
        ]

        mock_comment_publisher = MagicMock()
        bus = InMemoryCommandBus()

        service = ProcessIssueCommandsService(
            pr_repository=mock_pr_repository,
            comment_reader=mock_comment_reader,
            comment_publisher=mock_comment_publisher,
            issue_command_parser=IssueCommandParser(),
            command_bus=bus,
        )

        service.execute(
            ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha)
        )

        mock_comment_publisher.post.assert_called_once()

    @pytest.fixture
    def _pr_id(self) -> PullRequestId:
        return PullRequestId(repository="owner/repo", number=42)

    @pytest.fixture
    def _sha(self) -> CommitSha:
        return CommitSha(value="abc1234")

    @pytest.fixture
    def _item(self) -> ReviewItem:
        return ReviewItem(
            id="id-1",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="x.py",
            description="broken code",
        )

    @pytest.fixture
    def _pr_with_review(
        self, _pr_id: PullRequestId, _sha: CommitSha, _item: ReviewItem
    ) -> PullRequest:
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="Found issues",
            summary="Review summary",
            model_used="model",
            items=[_item],
        )
        return PullRequest(id=_pr_id, title="Test PR", head_sha=_sha).add_review(
            review, _sha
        )
