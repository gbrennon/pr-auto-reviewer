"""Application-layer tests for ProcessIssueCommandsService using injected stubs."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pr_auto_reviewer.application.commands.process_issue_commands_command import (
    ProcessIssueCommandsCommand,
)
from pr_auto_reviewer.application.services import ProcessIssueCommandsService
from pr_auto_reviewer.application.serializers.issue_body_builder import (
    IssueBodyBuilder,
)
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
from pr_auto_reviewer.domain.services.issue_command_parser import IssueCommandParser
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser

from tests.pr_auto_reviewer.application.stubs import (
    StubPullRequestRepository,
    StubReviewReader,
    StubCommentReader,
    StubCommentPublisher,
    StubIssueTracker,
)


class TestProcessIssueCommandsService:
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
        return ReviewItem(
            number=1,
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="broken",
        )

    def test_processes_issue_command_and_creates_issues(self, _pr_id, _sha, _pr, _item):
        pr_repo = StubPullRequestRepository(initial=_pr)
        review_reader = StubReviewReader(body="1. **MAJOR** [bug] `x.py`: broken")
        comment_reader = StubCommentReader(
            [
                PrComment(
                    id=CommentId(value="c1"),
                    body="/create-issue 1",
                    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                )
            ]
        )
        comment_publisher = StubCommentPublisher()
        tracker = StubIssueTracker(
            [
                Issue(
                    id=101,
                    repository="owner/repo",
                    title="[MAJOR] bug: broken",
                    body="body",
                    source_pr_id=_pr_id,
                    source_item_number=1,
                )
            ]
        )

        svc = ProcessIssueCommandsService(
            pr_repo,
            review_reader,
            comment_reader,
            comment_publisher,
            tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

        assert len(tracker.create_calls) == 1
        assert len(comment_publisher.post_calls) == 1

    def test_skips_already_processed_comment(self, _pr_id, _sha, _pr, _item):
        processed = _pr.mark_comment_processed(CommentId(value="c1"))
        pr_repo = StubPullRequestRepository(initial=processed)
        review_reader = StubReviewReader(body="1. **MAJOR** [bug] `x.py`: broken")
        comment_reader = StubCommentReader(
            [
                PrComment(
                    id=CommentId(value="c1"),
                    body="/create-issue 1",
                    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                )
            ]
        )
        comment_publisher = StubCommentPublisher()
        tracker = StubIssueTracker()

        svc = ProcessIssueCommandsService(
            pr_repo,
            review_reader,
            comment_reader,
            comment_publisher,
            tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

        assert len(tracker.create_calls) == 0

    def test_noop_when_no_review(self, _pr_id, _sha, _pr):
        pr_repo = StubPullRequestRepository(initial=_pr)
        review_reader = StubReviewReader(body=None)
        tracker = StubIssueTracker()

        svc = ProcessIssueCommandsService(
            pr_repo,
            review_reader,
            StubCommentReader(),
            StubCommentPublisher(),
            tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))
        assert len(tracker.create_calls) == 0

    def test_noop_when_no_comments(self, _pr_id, _sha, _pr):
        pr_repo = StubPullRequestRepository(initial=_pr)
        review_reader = StubReviewReader(body="1. **MAJOR** [bug] `x.py`: broken")
        comment_reader = StubCommentReader([])
        tracker = StubIssueTracker()

        svc = ProcessIssueCommandsService(
            pr_repo,
            review_reader,
            comment_reader,
            StubCommentPublisher(),
            tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))
        assert len(tracker.create_calls) == 0

    def test_raises_when_pr_not_found(self, _pr_id, _sha):
        pr_repo = StubPullRequestRepository(initial=None)
        svc = ProcessIssueCommandsService(
            pr_repo,
            StubReviewReader(),
            StubCommentReader(),
            StubCommentPublisher(),
            StubIssueTracker(),
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        with pytest.raises(PullRequestNotFoundError):
            svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

    def test_noop_when_review_items_empty(self, _pr_id, _sha, _pr):
        """When review body parses to zero items, execution returns early."""
        pr_repo = StubPullRequestRepository(initial=_pr)
        review_reader = StubReviewReader(body="No structured review items")
        svc = ProcessIssueCommandsService(
            pr_repo,
            review_reader,
            StubCommentReader(),
            StubCommentPublisher(),
            StubIssueTracker(),
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))
        # No exception, just early return

    def test_skips_non_command_comment(self, _pr_id, _sha, _pr, _item):
        """A regular comment without /create-issue syntax is skipped."""
        pr_repo = StubPullRequestRepository(initial=_pr)
        review_reader = StubReviewReader(body="1. **MAJOR** [bug] `x.py`: broken")
        comment_reader = StubCommentReader(
            [
                PrComment(
                    id=CommentId(value="c2"),
                    body="This is just a regular comment",
                    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                )
            ]
        )
        comment_publisher = StubCommentPublisher()
        tracker = StubIssueTracker()
        svc = ProcessIssueCommandsService(
            pr_repo,
            review_reader,
            comment_reader,
            comment_publisher,
            tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))
        assert len(tracker.create_calls) == 0

    def test_publishes_invalid_items_message(self, _pr_id, _sha, _pr, _item):
        """When comment references non-existent item numbers, error message posted."""
        pr_repo = StubPullRequestRepository(initial=_pr)
        review_reader = StubReviewReader(body="1. **MAJOR** [bug] `x.py`: broken")
        comment_reader = StubCommentReader(
            [
                PrComment(
                    id=CommentId(value="c2"),
                    body="/create-issue 99",
                    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                )
            ]
        )
        comment_publisher = StubCommentPublisher()
        tracker = StubIssueTracker()
        svc = ProcessIssueCommandsService(
            pr_repo,
            review_reader,
            comment_reader,
            comment_publisher,
            tracker,
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))
        assert len(comment_publisher.post_calls) == 1
        assert len(tracker.create_calls) == 0

    def test_raises_on_issue_creation_error(self, _pr_id, _sha, _pr, _item):
        """When issue tracker raises IssueCreationError, it is re-raised."""
        pr_repo = StubPullRequestRepository(initial=_pr)
        review_reader = StubReviewReader(body="1. **MAJOR** [bug] `x.py`: broken")
        comment_reader = StubCommentReader(
            [
                PrComment(
                    id=CommentId(value="c2"),
                    body="/create-issue 1",
                    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                )
            ]
        )
        comment_publisher = StubCommentPublisher()

        class RaisingIssueTracker(StubIssueTracker):
            def create(self, repository, title, body):
                raise IssueCreationError(
                    repository=repository, item_number=1, reason="test error"
                )

        svc = ProcessIssueCommandsService(
            pr_repo,
            review_reader,
            comment_reader,
            comment_publisher,
            RaisingIssueTracker(),
            ReviewItemParser(),
            IssueCommandParser(),
            IssueBodyBuilder(),
        )
        with pytest.raises(IssueCreationError):
            svc.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))
