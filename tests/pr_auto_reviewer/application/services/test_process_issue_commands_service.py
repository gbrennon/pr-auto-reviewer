"""Application-layer tests for ProcessIssueCommandsService using injected mocks."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pr_auto_reviewer.application.serializers.issue_body_builder import (
    IssueBodyBuilder,
)
from pr_auto_reviewer.application.services import ProcessIssueCommandsService
from pr_auto_reviewer.domain import (
    CommentId,
    CommitSha,
    Issue,
    IssueCreationError,
    ItemSeverity,
    PrComment,
    PullRequest,
    PullRequestId,
    PullRequestNotFoundError,
    ReviewItem,
)
from pr_auto_reviewer.domain.messages.commands.process_issue_commands_command import (
    ProcessIssueCommandsCommand,
)
from pr_auto_reviewer.domain.services.issue_command_parser import IssueCommandParser
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser


class TestProcessIssueCommandsService:

    def test_processes_issue_command_and_creates_issues(
        self, _pr_id, _sha, _pr, _item,
        mock_pr_repository, mock_review_reader, mock_comment_reader,
        mock_comment_publisher, mock_issue_tracker,
    ):
        mock_pr_repository.find.return_value = _pr
        mock_review_reader.get_latest_review.return_value = (
            "1. [bug] [MAJOR] x.py\n\nbroken"
        )
        # Parse the review to get the actual generated ID
        parser = ReviewItemParser()
        items = parser.parse(mock_review_reader.get_latest_review.return_value)
        generated_id = items[0].id
        
        mock_comment_reader.get_comments.return_value = [
            PrComment(
                id=CommentId(value="c1"),
                body=f"/create issue {generated_id}",
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
            )
        ]
        mock_issue_tracker.create.return_value = Issue(
            id=101,
            repository="owner/repo",
            title="[MAJOR] bug: broken",
            body="body",
            source_pr_id=_pr_id,
            source_item_id=generated_id,
        )

        svc = ProcessIssueCommandsService(
            mock_pr_repository,
            mock_review_reader,
            mock_comment_reader,
            mock_comment_publisher,
            mock_issue_tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

        mock_issue_tracker.create.assert_called_once()
        mock_comment_publisher.post.assert_called_once()

    def test_skips_already_processed_comment(
        self, _pr_id, _sha, _pr, _item,
        mock_pr_repository, mock_review_reader, mock_comment_reader,
        mock_comment_publisher, mock_issue_tracker,
    ):
        processed = _pr.mark_comment_processed(CommentId(value="c1"))
        mock_pr_repository.find.return_value = processed
        mock_review_reader.get_latest_review.return_value = (
            "1. [bug] [MAJOR] x.py\n\nbroken"
        )
        # Parse the review to get the actual generated ID
        parser = ReviewItemParser()
        items = parser.parse(mock_review_reader.get_latest_review.return_value)
        generated_id = items[0].id
        
        mock_comment_reader.get_comments.return_value = [
            PrComment(
                id=CommentId(value="c1"),
                body=f"/create-issue {generated_id}",
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
            )
        ]

        svc = ProcessIssueCommandsService(
            mock_pr_repository,
            mock_review_reader,
            mock_comment_reader,
            mock_comment_publisher,
            mock_issue_tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

        mock_issue_tracker.create.assert_not_called()

    def test_noop_when_no_review(
        self, _pr_id, _sha, _pr,
        mock_pr_repository, mock_review_reader, mock_comment_reader,
        mock_comment_publisher, mock_issue_tracker,
    ):
        mock_pr_repository.find.return_value = _pr
        mock_review_reader.get_latest_review.return_value = None

        svc = ProcessIssueCommandsService(
            mock_pr_repository,
            mock_review_reader,
            mock_comment_reader,
            mock_comment_publisher,
            mock_issue_tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))
        mock_issue_tracker.create.assert_not_called()

    def test_noop_when_no_comments(
        self, _pr_id, _sha, _pr,
        mock_pr_repository, mock_review_reader, mock_comment_reader,
        mock_comment_publisher, mock_issue_tracker,
    ):
        mock_pr_repository.find.return_value = _pr
        mock_review_reader.get_latest_review.return_value = (
            "1. [bug] [MAJOR] x.py\n\nbroken"
        )
        mock_comment_reader.get_comments.return_value = []

        svc = ProcessIssueCommandsService(
            mock_pr_repository,
            mock_review_reader,
            mock_comment_reader,
            mock_comment_publisher,
            mock_issue_tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))
        mock_issue_tracker.create.assert_not_called()

    def test_raises_when_pr_not_found(
        self, _pr_id, _sha,
        mock_pr_repository, mock_review_reader, mock_comment_reader,
        mock_comment_publisher, mock_issue_tracker,
    ):
        mock_pr_repository.find.return_value = None
        svc = ProcessIssueCommandsService(
            mock_pr_repository,
            mock_review_reader,
            mock_comment_reader,
            mock_comment_publisher,
            mock_issue_tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        with pytest.raises(PullRequestNotFoundError):
            svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

    def test_noop_when_review_items_empty(
        self, _pr_id, _sha, _pr,
        mock_pr_repository, mock_review_reader, mock_comment_reader,
        mock_comment_publisher, mock_issue_tracker,
    ):
        """When review body parses to zero items, execution returns early."""
        mock_pr_repository.find.return_value = _pr
        mock_review_reader.get_latest_review.return_value = (
            "No structured review items"
        )
        svc = ProcessIssueCommandsService(
            mock_pr_repository,
            mock_review_reader,
            mock_comment_reader,
            mock_comment_publisher,
            mock_issue_tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))
        mock_issue_tracker.create.assert_not_called()

    def test_skips_non_command_comment(
        self, _pr_id, _sha, _pr, _item,
        mock_pr_repository, mock_review_reader, mock_comment_reader,
        mock_comment_publisher, mock_issue_tracker,
    ):
        """A regular comment without /create-issue syntax is skipped."""
        mock_pr_repository.find.return_value = _pr
        mock_review_reader.get_latest_review.return_value = (
            "1. [bug] [MAJOR] x.py\n\nbroken"
        )
        mock_comment_reader.get_comments.return_value = [
            PrComment(
                id=CommentId(value="c2"),
                body="This is just a regular comment",
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
            )
        ]
        svc = ProcessIssueCommandsService(
            mock_pr_repository,
            mock_review_reader,
            mock_comment_reader,
            mock_comment_publisher,
            mock_issue_tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))
        mock_issue_tracker.create.assert_not_called()

    def test_publishes_invalid_items_message(
        self, _pr_id, _sha, _pr, _item,
        mock_pr_repository, mock_review_reader, mock_comment_reader,
        mock_comment_publisher, mock_issue_tracker,
    ):
        """When comment references non-existent item numbers, error message posted."""
        mock_pr_repository.find.return_value = _pr
        mock_review_reader.get_latest_review.return_value = (
            "1. [bug] [MAJOR] x.py\n\nbroken"
        )
        mock_comment_reader.get_comments.return_value = [
            PrComment(
                id=CommentId(value="c2"),
                body="/create-issue invalid-id",
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
            )
        ]
        svc = ProcessIssueCommandsService(
            mock_pr_repository,
            mock_review_reader,
            mock_comment_reader,
            mock_comment_publisher,
            mock_issue_tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))
        mock_comment_publisher.post.assert_called_once()
        mock_issue_tracker.create.assert_not_called()

    def test_raises_on_issue_creation_error(
        self, _pr_id, _sha, _pr, _item,
        mock_pr_repository, mock_review_reader, mock_comment_reader,
        mock_comment_publisher, mock_issue_tracker,
    ):
        """When issue tracker raises IssueCreationError, it is re-raised."""
        mock_pr_repository.find.return_value = _pr
        mock_review_reader.get_latest_review.return_value = (
            "1. [bug] [MAJOR] x.py\n\nbroken"
        )
        # Parse the review to get the actual generated ID
        parser = ReviewItemParser()
        items = parser.parse(mock_review_reader.get_latest_review.return_value)
        generated_id = items[0].id
        
        mock_comment_reader.get_comments.return_value = [
            PrComment(
                id=CommentId(value="c2"),
                body=f"/create issue {generated_id}",
                created_at=datetime(2025, 1, 1, tzinfo=UTC),
            )
        ]
        mock_issue_tracker.create.side_effect = IssueCreationError(
            repository="owner/repo", item_number=1, reason="test error",
        )

        svc = ProcessIssueCommandsService(
            mock_pr_repository,
            mock_review_reader,
            mock_comment_reader,
            mock_comment_publisher,
            mock_issue_tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        with pytest.raises(IssueCreationError):
            svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))
    @pytest.fixture
    def _pr_id(self):
        return PullRequestId(repository="owner/repo", number=42)

    @pytest.fixture
    def _sha(self):
        return CommitSha(value="abc123")

    @pytest.fixture
    def _pr(self, _pr_id, _sha):
        return PullRequest(id=_pr_id, title="Test PR", head_sha=_sha)

    @pytest.fixture
    def _item(self):
        return ReviewItem(id="id-1",
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="broken",
        )
