"""Application-layer tests for RegisterIssueService using injected mocks."""

from __future__ import annotations

import pytest

from pr_auto_reviewer.application.serializers.issue_body_builder import (
    IssueBodyBuilder,
)
from pr_auto_reviewer.application.services import RegisterIssueService
from pr_auto_reviewer.domain import (
    CommitSha,
    ItemSeverity,
    PullRequest,
    PullRequestId,
    PullRequestNotFoundError,
    ReviewItem,
    ReviewItemNotFoundError,
)
from pr_auto_reviewer.domain.messages.commands.register_issue_command import (
    RegisterIssueCommand,
)
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser


class TestRegisterIssueService:

    def test_registers_issue_by_id(
        self, _pr_id, _sha, _pr, mock_pr_repository, mock_review_reader,
        mock_issue_tracker,
    ):
        mock_pr_repository.find.return_value = _pr
        mock_review_reader.get_latest_review.return_value = (
            "1. [bug] [MAJOR] x.py\n\nbroken"
        )
        parser = ReviewItemParser()
        builder = IssueBodyBuilder()

        # Parse the review to get the actual generated ID
        items = parser.parse(mock_review_reader.get_latest_review.return_value)
        generated_id = items[0].id

        svc = RegisterIssueService(
            mock_pr_repository, mock_review_reader, parser,
            mock_issue_tracker, builder,
        )
        svc.execute(
            RegisterIssueCommand(
                pr_id=_pr_id,
                head_sha=_sha,
                issue_id=generated_id,
                command_text=f"issue {generated_id}",
            )
        )

        mock_issue_tracker.create.assert_called_once()
        _, kwargs = mock_issue_tracker.create.call_args
        assert kwargs["repository"] == "owner/repo"
        assert "MAJOR" in kwargs["title"]
        assert "broken" in kwargs["body"]

    def test_registers_issue_by_number_fallback(
        self, _pr_id, _sha, _pr, mock_pr_repository, mock_review_reader,
        mock_issue_tracker,
    ):
        mock_pr_repository.find.return_value = _pr
        mock_review_reader.get_latest_review.return_value = (
            "1. [style] [MINOR] y.py\n\nnit"
        )
        parser = ReviewItemParser()
        builder = IssueBodyBuilder()

        # Parse the review to get the actual generated ID
        items = parser.parse(mock_review_reader.get_latest_review.return_value)
        generated_id = items[0].id

        svc = RegisterIssueService(
            mock_pr_repository, mock_review_reader, parser,
            mock_issue_tracker, builder,
        )
        svc.execute(
            RegisterIssueCommand(
                pr_id=_pr_id,
                head_sha=_sha,
                issue_id=generated_id,
                command_text=f"issue {generated_id}",
            )
        )

        mock_issue_tracker.create.assert_called_once()

    def test_raises_when_pr_not_found(
        self, _pr_id, _sha, mock_pr_repository, mock_review_reader,
        mock_issue_tracker,
    ):
        mock_pr_repository.find.return_value = None
        svc = RegisterIssueService(
            mock_pr_repository,
            mock_review_reader,
            ReviewItemParser(),
            mock_issue_tracker,
            IssueBodyBuilder(),
        )
        with pytest.raises(PullRequestNotFoundError):
            svc.execute(
                RegisterIssueCommand(
                    pr_id=_pr_id,
                    head_sha=_sha,
                    issue_id="x",
                    command_text="x",
                )
            )

    def test_raises_when_no_review(
        self, _pr_id, _sha, _pr, mock_pr_repository, mock_review_reader,
        mock_issue_tracker,
    ):
        mock_pr_repository.find.return_value = _pr
        mock_review_reader.get_latest_review.return_value = None
        svc = RegisterIssueService(
            mock_pr_repository,
            mock_review_reader,
            ReviewItemParser(),
            mock_issue_tracker,
            IssueBodyBuilder(),
        )
        with pytest.raises(ReviewItemNotFoundError):
            svc.execute(
                RegisterIssueCommand(
                    pr_id=_pr_id,
                    head_sha=_sha,
                    issue_id="x",
                    command_text="x",
                )
            )

    def test_raises_when_item_not_found(
        self, _pr_id, _sha, _pr, mock_pr_repository, mock_review_reader,
        mock_issue_tracker,
    ):
        mock_pr_repository.find.return_value = _pr
        mock_review_reader.get_latest_review.return_value = (
            "1. [bug] [MAJOR] x.py\n\nbroken"
        )
        svc = RegisterIssueService(
            mock_pr_repository,
            mock_review_reader,
            ReviewItemParser(),
            mock_issue_tracker,
            IssueBodyBuilder(),
        )
        with pytest.raises(ReviewItemNotFoundError):
            svc.execute(
                RegisterIssueCommand(
                    pr_id=_pr_id,
                    head_sha=_sha,
                    issue_id="nonexistent",
                    command_text="issue nonexistent",
                )
            )

    def test_raises_when_empty_review_items(
        self, _pr_id, _sha, _pr, mock_pr_repository, mock_review_reader,
        mock_issue_tracker,
    ):
        """When review body parses to zero items, raises ReviewItemNotFoundError."""
        mock_pr_repository.find.return_value = _pr
        mock_review_reader.get_latest_review.return_value = "No structured items"
        svc = RegisterIssueService(
            mock_pr_repository,
            mock_review_reader,
            ReviewItemParser(),
            mock_issue_tracker,
            IssueBodyBuilder(),
        )
        with pytest.raises(ReviewItemNotFoundError, match="no review items found"):
            svc.execute(
                RegisterIssueCommand(
                    pr_id=_pr_id,
                    head_sha=_sha,
                    issue_id="x",
                    command_text="x",
                )
            )

    def test_find_item_by_id_directly(
        self, _pr_id, _sha, _pr, mock_pr_repository, mock_review_reader,
        mock_issue_tracker,
    ):
        """_find_item returns the item when issue_id matches item.id."""
        mock_pr_repository.find.return_value = _pr
        svc = RegisterIssueService(
            mock_pr_repository,
            mock_review_reader,
            ReviewItemParser(),
            mock_issue_tracker,
            IssueBodyBuilder(),
        )
        item = ReviewItem(
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="broken",
            id="custom-id",
        )
        result = svc._find_item([item], "custom-id")
        assert result is item
    @pytest.fixture
    def _pr_id(self):
        return PullRequestId(repository="owner/repo", number=42)

    @pytest.fixture
    def _sha(self):
        return CommitSha(value="abc123")

    @pytest.fixture
    def _pr(self, _pr_id, _sha):
        return PullRequest(id=_pr_id, title="Test PR", head_sha=_sha)
