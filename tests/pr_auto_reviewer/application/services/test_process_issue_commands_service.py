"""Application-layer tests for ProcessIssueCommandsService."""

from __future__ import annotations

from datetime import UTC, datetime

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


class FakePullRequestRepository:
    """Fake PR repository that exposes saved state for assertions."""

    def __init__(self, initial: PullRequest | None = None) -> None:
        self._pr = initial
        self.save_calls: list[PullRequest] = []

    def find(self, pr_id: PullRequestId) -> PullRequest | None:
        return self._pr

    def save(self, pr: PullRequest) -> None:
        self.save_calls.append(pr)
        self._pr = pr

    def reset(self) -> None:
        self._pr = None


class FakeCommentReader:
    """Fake reader returning a preconfigured comment list."""

    def __init__(self, comments: list[PrComment]) -> None:
        self._comments = comments
        self.get_comments_calls: list[PullRequestId] = []

    def get_comments(self, pr_id: PullRequestId) -> list[PrComment]:
        self.get_comments_calls.append(pr_id)
        return list(self._comments)


class FakeCommentPublisher:
    """Fake publisher recording post bodies."""

    def __init__(self) -> None:
        self.post_calls: list[tuple[PullRequestId, str]] = []

    def post(self, pr_id: PullRequestId, body: str) -> None:
        self.post_calls.append((pr_id, body))


class TestProcessIssueCommandsService:
    def test_processes_issue_command_and_dispatches_creations(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
        _pr_with_review: PullRequest,
        _item: ReviewItem,
    ) -> None:
        fake_repo = FakePullRequestRepository(_pr_with_review)
        fake_reader = FakeCommentReader(
            [
                PrComment(
                    id=CommentId(value="c1"),
                    body=f"create issue {_item.id}",
                    created_at=datetime(2025, 1, 1, tzinfo=UTC),
                )
            ]
        )
        fake_publisher = FakeCommentPublisher()
        bus = InMemoryCommandBus()
        created_issue = Issue(
            id=101,
            repository="owner/repo",
            title="[MAJOR] bug: broken",
            body="body",
            source_pr_id=_pr_id,
            source_item_id=_item.id,
        )
        dispatched: list[RegisterIssueCommand] = []

        def handle_register(command: RegisterIssueCommand) -> Issue:
            dispatched.append(command)
            return created_issue

        bus.register(RegisterIssueCommand, handle_register)
        service = ProcessIssueCommandsService(
            pr_repository=fake_repo,
            comment_reader=fake_reader,
            comment_publisher=fake_publisher,
            issue_command_parser=IssueCommandParser(),
            command_bus=bus,
        )

        service.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

        assert len(dispatched) == 1
        assert dispatched[0].issue_id == _item.id
        assert dispatched[0].pr_id == _pr_id
        assert len(fake_publisher.post_calls) == 1
        assert len(fake_repo.save_calls) == 1
        assert CommentId(value="c1") in fake_repo.save_calls[0].processed_comment_ids
        assert fake_repo.save_calls[0].processed_comment_ids == frozenset(
            {CommentId(value="c1")}
        )

    def test_host_does_not_affect_process_command_logic(
        self, _sha: CommitSha, _item: ReviewItem
    ) -> None:
        for repository in ["owner/repo", "forgejo-owner/other-repo"]:
            pr_id = PullRequestId(repository=repository, number=42)
            review = CodeReview(
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                reason="Found issues",
                summary="Review summary",
                model_used="model",
                items=[_item],
            )
            pr = PullRequest(id=pr_id, title="Test PR", head_sha=_sha).add_review(
                review, _sha
            )
            fake_repo = FakePullRequestRepository(pr)
            fake_reader = FakeCommentReader(
                [
                    PrComment(
                        id=CommentId(value="c1"),
                        body=f"create issue {_item.id}",
                        created_at=datetime(2025, 1, 1, tzinfo=UTC),
                    )
                ]
            )
            fake_publisher = FakeCommentPublisher()
            bus = InMemoryCommandBus()
            dispatched: list[RegisterIssueCommand] = []

            def handle_register(command: RegisterIssueCommand) -> Issue:
                dispatched.append(command)
                return Issue(
                    id=1,
                    repository=command.pr_id.repository,
                    title="t",
                    body="b",
                    source_pr_id=command.pr_id,
                    source_item_id=command.issue_id,
                )

            bus.register(RegisterIssueCommand, handle_register)
            service = ProcessIssueCommandsService(
                pr_repository=fake_repo,
                comment_reader=fake_reader,
                comment_publisher=fake_publisher,
                issue_command_parser=IssueCommandParser(),
                command_bus=bus,
            )

            service.execute(ProcessIssueCommandsCommand(pr_id=pr_id, head_sha=_sha))

            assert dispatched[0].pr_id.repository == repository
            assert len(fake_publisher.post_calls) == 1
            assert CommentId(value="c1") in fake_repo.save_calls[0].processed_comment_ids

    def test_skips_already_processed_comment(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
        _pr_with_review: PullRequest,
        _item: ReviewItem,
    ) -> None:
        processed_pr = _pr_with_review.mark_comment_processed(CommentId(value="c1"))
        fake_repo = FakePullRequestRepository(processed_pr)
        fake_reader = FakeCommentReader(
            [
                PrComment(
                    id=CommentId(value="c1"),
                    body=f"create issue {_item.id}",
                    created_at=datetime(2025, 1, 1, tzinfo=UTC),
                )
            ]
        )
        fake_publisher = FakeCommentPublisher()
        bus = InMemoryCommandBus()
        service = ProcessIssueCommandsService(
            pr_repository=fake_repo,
            comment_reader=fake_reader,
            comment_publisher=fake_publisher,
            issue_command_parser=IssueCommandParser(),
            command_bus=bus,
        )

        service.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

        assert len(fake_publisher.post_calls) == 0
        assert len(fake_reader.get_comments_calls) == 1

    def test_noop_when_no_review_items(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
    ) -> None:
        empty_pr = PullRequest(id=_pr_id, title="Test PR", head_sha=_sha)
        fake_repo = FakePullRequestRepository(empty_pr)
        fake_reader = FakeCommentReader([])
        fake_publisher = FakeCommentPublisher()
        bus = InMemoryCommandBus()
        service = ProcessIssueCommandsService(
            pr_repository=fake_repo,
            comment_reader=fake_reader,
            comment_publisher=fake_publisher,
            issue_command_parser=IssueCommandParser(),
            command_bus=bus,
        )

        service.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

        assert len(fake_reader.get_comments_calls) == 0
        assert len(fake_publisher.post_calls) == 0
        assert len(fake_repo.save_calls) == 0

    def test_noop_when_no_comments(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
        _pr_with_review: PullRequest,
    ) -> None:
        fake_repo = FakePullRequestRepository(_pr_with_review)
        fake_reader = FakeCommentReader([])
        fake_publisher = FakeCommentPublisher()
        bus = InMemoryCommandBus()
        service = ProcessIssueCommandsService(
            pr_repository=fake_repo,
            comment_reader=fake_reader,
            comment_publisher=fake_publisher,
            issue_command_parser=IssueCommandParser(),
            command_bus=bus,
        )

        service.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

        assert len(fake_publisher.post_calls) == 0
        assert len(fake_repo.save_calls) == 0

    def test_raises_when_pr_not_found(
        self, _pr_id: PullRequestId, _sha: CommitSha
    ) -> None:
        fake_repo = FakePullRequestRepository(None)
        service = ProcessIssueCommandsService(
            pr_repository=fake_repo,
            comment_reader=FakeCommentReader([]),
            comment_publisher=FakeCommentPublisher(),
            issue_command_parser=IssueCommandParser(),
            command_bus=InMemoryCommandBus(),
        )

        with pytest.raises(PullRequestNotFoundError):
            service.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

    def test_skips_non_command_comment(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
        _pr_with_review: PullRequest,
    ) -> None:
        fake_repo = FakePullRequestRepository(_pr_with_review)
        fake_reader = FakeCommentReader(
            [
                PrComment(
                    id=CommentId(value="c2"),
                    body="This is a regular discussion comment",
                    created_at=datetime(2025, 1, 1, tzinfo=UTC),
                )
            ]
        )
        fake_publisher = FakeCommentPublisher()
        bus = InMemoryCommandBus()
        service = ProcessIssueCommandsService(
            pr_repository=fake_repo,
            comment_reader=fake_reader,
            comment_publisher=fake_publisher,
            issue_command_parser=IssueCommandParser(),
            command_bus=bus,
        )

        service.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

        assert len(fake_publisher.post_calls) == 0

    def test_publishes_invalid_items_message(
        self,
        _pr_id: PullRequestId,
        _sha: CommitSha,
        _pr_with_review: PullRequest,
    ) -> None:
        fake_repo = FakePullRequestRepository(_pr_with_review)
        fake_reader = FakeCommentReader(
            [
                PrComment(
                    id=CommentId(value="c2"),
                    body="create issue invalid-id",
                    created_at=datetime(2025, 1, 1, tzinfo=UTC),
                )
            ]
        )
        fake_publisher = FakeCommentPublisher()
        bus = InMemoryCommandBus()
        service = ProcessIssueCommandsService(
            pr_repository=fake_repo,
            comment_reader=fake_reader,
            comment_publisher=fake_publisher,
            issue_command_parser=IssueCommandParser(),
            command_bus=bus,
        )

        service.execute(ProcessIssueCommandsCommand(pr_id=_pr_id, head_sha=_sha))

        assert len(fake_publisher.post_calls) == 1

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
