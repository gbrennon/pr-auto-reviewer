"""Application-layer tests for RegisterIssueService using injected stubs."""

from __future__ import annotations

import pytest

from pr_auto_reviewer.domain.messages.commands.register_issue_command import (
    RegisterIssueCommand,
)
from pr_auto_reviewer.application.services import RegisterIssueService
from pr_auto_reviewer.application.serializers.issue_body_builder import (
    IssueBodyBuilder,
)
from pr_auto_reviewer.domain import (
    CommitSha,
    Issue,
    ItemSeverity,
    PullRequest,
    PullRequestId,
    PullRequestNotFoundError,
    ReviewItemNotFoundError,
    ReviewItem,
)
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser

from tests.pr_auto_reviewer.application.stubs import (
    StubPullRequestRepository,
    StubReviewReader,
    StubIssueTracker,
)


class TestRegisterIssueService:

    def test_registers_issue_by_id(self, _pr_id, _sha, _pr):
        item = ReviewItem(
            number=1,
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="broken",
            id="a3f2",
        )
        pr_repo = StubPullRequestRepository(initial=_pr)
        review_reader = StubReviewReader(body="1. [bug] [MAJOR] x.py\n\nbroken")
        parser = ReviewItemParser()
        tracker = StubIssueTracker()
        builder = IssueBodyBuilder()

        svc = RegisterIssueService(pr_repo, review_reader, parser, tracker, builder)
        svc.execute(
            RegisterIssueCommand(
                pr_id=_pr_id,
                head_sha=_sha,
                issue_id="1",
                command_text="issue 1",
            )
        )

        assert len(tracker.create_calls) == 1
        repo, title, body = tracker.create_calls[0]
        assert repo == "owner/repo"
        assert "MAJOR" in title
        assert "broken" in body

    def test_registers_issue_by_number_fallback(self, _pr_id, _sha, _pr):
        item = ReviewItem(
            number=1,
            severity=ItemSeverity.MINOR,
            category="style",
            file_path="y.py",
            description="nit",
            id="",
        )
        pr_repo = StubPullRequestRepository(initial=_pr)
        review_reader = StubReviewReader(body="1. [style] [MINOR] y.py\n\nnit")
        parser = ReviewItemParser()
        tracker = StubIssueTracker()
        builder = IssueBodyBuilder()

        svc = RegisterIssueService(pr_repo, review_reader, parser, tracker, builder)
        svc.execute(
            RegisterIssueCommand(
                pr_id=_pr_id,
                head_sha=_sha,
                issue_id="1",
                command_text="issue 1",
            )
        )

        assert len(tracker.create_calls) == 1

    def test_raises_when_pr_not_found(self, _pr_id, _sha):
        pr_repo = StubPullRequestRepository(initial=None)
        svc = RegisterIssueService(
            pr_repo,
            StubReviewReader(),
            ReviewItemParser(),
            StubIssueTracker(),
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

    def test_raises_when_no_review(self, _pr_id, _sha, _pr):
        pr_repo = StubPullRequestRepository(initial=_pr)
        review_reader = StubReviewReader(body=None)
        svc = RegisterIssueService(
            pr_repo,
            review_reader,
            ReviewItemParser(),
            StubIssueTracker(),
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

    def test_raises_when_item_not_found(self, _pr_id, _sha, _pr):
        pr_repo = StubPullRequestRepository(initial=_pr)
        review_reader = StubReviewReader(body="1. [bug] [MAJOR] x.py\n\nbroken")
        svc = RegisterIssueService(
            pr_repo,
            review_reader,
            ReviewItemParser(),
            StubIssueTracker(),
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

    def test_raises_when_empty_review_items(self, _pr_id, _sha, _pr):
        """When review body parses to zero items, raises ReviewItemNotFoundError."""
        pr_repo = StubPullRequestRepository(initial=_pr)
        review_reader = StubReviewReader(body="No structured items")
        svc = RegisterIssueService(
            pr_repo,
            review_reader,
            ReviewItemParser(),
            StubIssueTracker(),
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

    def test_find_item_by_id_directly(self, _pr_id, _sha, _pr):
        """_find_item returns the item when issue_id matches item.id."""
        pr_repo = StubPullRequestRepository(initial=_pr)
        svc = RegisterIssueService(
            pr_repo,
            StubReviewReader(body=None),
            ReviewItemParser(),
            StubIssueTracker(),
            IssueBodyBuilder(),
        )
        item = ReviewItem(
            number=1,
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
