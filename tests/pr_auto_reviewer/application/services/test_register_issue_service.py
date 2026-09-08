"""Application-layer tests for RegisterIssueService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pr_auto_reviewer.application.services.register_issue_service import (
    RegisterIssueService,
)
from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.entities.pull_request import PullRequest
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions import (
    PullRequestNotFoundError,
    ReviewItemNotFoundError,
)
from pr_auto_reviewer.domain.messages.commands.register_issue_command import (
    RegisterIssueCommand,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.issue_content import IssueContent
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


class TestRegisterIssueService:

    def test_registers_issue_by_item_id(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
        _item: ReviewItem,
        _review: CodeReview,
    ) -> None:
        pr = PullRequest(id=_pr_id, title="Test PR", head_sha=_sha).add_review(
            _review, _sha
        )
        mock_pr_repository = MagicMock()
        mock_pr_repository.find.return_value = pr

        mock_content_preparer = MagicMock()
        mock_content_preparer.execute.return_value = IssueContent(
            title="Prepared Title", body="Prepared Body"
        )

        expected_issue = Issue(
            id=101,
            repository="owner/repo",
            title="Prepared Title",
            body="Prepared Body",
            source_pr_id=_pr_id,
            source_item_id=_item.id,
        )
        mock_issue_tracker = MagicMock()
        mock_issue_tracker.create.return_value = expected_issue

        service = RegisterIssueService(
            pr_repository=mock_pr_repository,
            issue_content_preparer=mock_content_preparer,
            issue_tracker=mock_issue_tracker,
        )

        result = service.execute(
            RegisterIssueCommand(pr_id=_pr_id, issue_id=_item.id)
        )

        assert result is expected_issue
        mock_issue_tracker.create.assert_called_once_with(
            repository="owner/repo",
            title="Prepared Title",
            body="Prepared Body",
            source_item_id=_item.id,
        )

    def test_raises_when_pr_not_found(
        self, _pr_id: PullRequestId
    ) -> None:
        mock_pr_repository = MagicMock()
        mock_pr_repository.find.return_value = None
        mock_content_preparer = MagicMock()
        mock_issue_tracker = MagicMock()

        service = RegisterIssueService(
            pr_repository=mock_pr_repository,
            issue_content_preparer=mock_content_preparer,
            issue_tracker=mock_issue_tracker,
        )

        with pytest.raises(PullRequestNotFoundError):
            service.execute(
                RegisterIssueCommand(pr_id=_pr_id, issue_id="item-1")
            )

    def test_raises_when_item_not_found(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
        _review: CodeReview,
    ) -> None:
        pr = PullRequest(id=_pr_id, title="Test PR", head_sha=_sha).add_review(
            _review, _sha
        )
        mock_pr_repository = MagicMock()
        mock_pr_repository.find.return_value = pr
        mock_content_preparer = MagicMock()
        mock_issue_tracker = MagicMock()

        service = RegisterIssueService(
            pr_repository=mock_pr_repository,
            issue_content_preparer=mock_content_preparer,
            issue_tracker=mock_issue_tracker,
        )

        with pytest.raises(ReviewItemNotFoundError):
            service.execute(
                RegisterIssueCommand(pr_id=_pr_id, issue_id="nonexistent-id")
            )

    def test_find_item_by_id_directly(self, _item: ReviewItem) -> None:
        result = RegisterIssueService._find_item([_item], _item.id)
        assert result is _item

    def test_find_item_raises_when_absent(self, _item: ReviewItem) -> None:
        with pytest.raises(ReviewItemNotFoundError):
            RegisterIssueService._find_item([_item], "absent-id")

    @pytest.fixture
    def _pr_id(self) -> PullRequestId:
        return PullRequestId(repository="owner/repo", number=42)

    @pytest.fixture
    def _sha(self) -> CommitSha:
        return CommitSha(value="abc1234")

    @pytest.fixture
    def _item(self) -> ReviewItem:
        return ReviewItem(
            id="item-1",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="src/main.py",
            description="Null check missing",
        )

    @pytest.fixture
    def _review(self, _item: ReviewItem) -> CodeReview:
        return CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="Found bugs",
            summary="Review completed",
            model_used="test-model",
            items=[_item],
        )
