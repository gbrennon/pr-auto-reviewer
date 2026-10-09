from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pr_auto_reviewer.application.services.process_issue_commands_service import (
    ProcessIssueCommandsService,
)
from pr_auto_reviewer.domain.entities.pull_request import PullRequest
from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.register_issue_command import (
    RegisterIssueCommand,
)
from pr_auto_reviewer.domain.services.issue_command_parser import IssueCommandParser
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.comment_id import CommentId
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pr_comment import PrComment
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_item_status import ReviewItemStatus
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyRenderer,
)
from pr_auto_reviewer.presentation.cli.runner import CliRunner
from pr_auto_reviewer.presentation.ports import OpenPullRequest
from pr_auto_reviewer.presentation.ports.pr_lister_port import PrListerPort
from tests.e2e.test_cli_flows_with_fakes import (
    FakeReviewReader,
    FakeReviewService,
)
from tests.fakes.fake_forgejo_pr_lister import FakeForgejoPrLister
from tests.fakes.fake_notifier import FakeNotifier
from tests.fakes.fake_pull_request_repository import FakePullRequestRepository
from tests.pr_auto_reviewer.application.services.test_process_issue_commands_service import (
    FakeCommentPublisher,
    FakeCommentReader,
)


_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "pr_auto_reviewer"
    / "infrastructure"
    / "templates"
)


def test_cli_command_processing_publishes_dismissed_suggestion_status() -> None:
    pr_id = PullRequestId(repository="forgejo:owner/repo", number=4)
    sha = CommitSha("abc123")
    suggestion = ReviewItem(
        id="suggestion-1",
        severity=ItemSeverity.INFO,
        category=IssueCategory.GENERAL,
        file_path="src/example.py",
        description="Prefer a named helper.",
    )
    review = CodeReview(
        verdict=ReviewVerdict.APPROVED,
        reason="No blocking issues remain.",
        summary="The review contains one suggestion.",
        suggestions=[suggestion],
        model_used="e2e-test",
    )
    initial_pr = PullRequest(
        id=pr_id,
        title="Suggestion status flow",
        head_sha=sha,
    ).add_review(review, sha)
    repository = FakePullRequestRepository(initial_pr)
    comment = PrComment(
        id=CommentId(value="comment-1"),
        body="dismiss suggestion-1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    command_service = ProcessIssueCommandsService(
        pr_repository=repository,
        comment_reader=FakeCommentReader([comment]),
        comment_publisher=FakeCommentPublisher(),
        issue_command_parser=IssueCommandParser(),
        command_bus=InMemoryCommandBus(),
    )
    review_service = FakeReviewService([])
    open_pr = OpenPullRequest(
        pr_id=pr_id,
        head_sha=sha,
        title=initial_pr.title,
        description="",
        is_draft=False,
        review_requested=False,
        target_branch="main",
    )
    runner = CliRunner(
        review_service=review_service,
        process_commands_service=command_service,
        review_reader=FakeReviewReader("review body"),
        pr_lister=cast(PrListerPort, FakeForgejoPrLister([open_pr])),
        review_item_parser=ReviewItemParser(),
        pr_repository=repository,
        notifier=FakeNotifier(),
        output_mode="forgejo",
    )

    process_result = runner.run([
        "pr-auto-reviewer",
        "process-commands",
        "--repo",
        "forgejo:owner/repo",
        "--pr",
        "4",
    ])
    review_result = runner.run([
        "pr-auto-reviewer",
        "review",
        "--repo",
        "forgejo:owner/repo",
        "--pr",
        "4",
        "--force",
    ])

    saved_pr = repository.find(pr_id)
    assert process_result == 0
    assert review_result == 0
    assert saved_pr is not None
    updated_items = saved_pr.latest_review_items()
    assert updated_items[0].status is ReviewItemStatus.DISMISSED
    published_review = replace(
        review,
        suggestions=[updated_items[0]],
    )
    published_body = ReviewBodyRenderer(_TEMPLATE_DIR).render(published_review)

    assert review_service.executed_commands[0].force is True
    assert "`suggestion-1`. [DISMISSED] src/example.py" in published_body


def test_cli_command_processing_creates_issue_for_open_suggestion() -> None:
    pr_id = PullRequestId(repository="forgejo:owner/repo", number=4)
    sha = CommitSha("abc123")
    suggestion = ReviewItem(
        id="suggestion-1",
        severity=ItemSeverity.INFO,
        category=IssueCategory.GENERAL,
        file_path="src/example.py",
        description="Prefer a named helper.",
    )
    review = CodeReview(
        verdict=ReviewVerdict.APPROVED,
        reason="No blocking issues remain.",
        summary="The review contains one suggestion.",
        suggestions=[suggestion],
        model_used="e2e-test",
    )
    initial_pr = PullRequest(
        id=pr_id,
        title="Suggestion issue flow",
        head_sha=sha,
    ).add_review(review, sha)
    repository = FakePullRequestRepository(initial_pr)
    comment = PrComment(
        id=CommentId(value="comment-1"),
        body="create issue suggestion-1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    created_issue = Issue(
        id=101,
        repository="owner/repo",
        title="[INFO] suggestion",
        body="Prefer a named helper.",
        source_pr_id=pr_id,
        source_item_id=suggestion.id,
    )
    command_bus = InMemoryCommandBus()
    command_bus.register(RegisterIssueCommand, lambda _command: created_issue)
    comment_publisher = FakeCommentPublisher()
    command_service = ProcessIssueCommandsService(
        pr_repository=repository,
        comment_reader=FakeCommentReader([comment]),
        comment_publisher=comment_publisher,
        issue_command_parser=IssueCommandParser(),
        command_bus=command_bus,
    )
    review_service = FakeReviewService([])
    open_pr = OpenPullRequest(
        pr_id=pr_id,
        head_sha=sha,
        title=initial_pr.title,
        description="",
        is_draft=False,
        review_requested=False,
        target_branch="main",
    )
    runner = CliRunner(
        review_service=review_service,
        process_commands_service=command_service,
        review_reader=FakeReviewReader("review body"),
        pr_lister=cast(PrListerPort, FakeForgejoPrLister([open_pr])),
        review_item_parser=ReviewItemParser(),
        pr_repository=repository,
        notifier=FakeNotifier(),
        output_mode="forgejo",
    )

    process_result = runner.run([
        "pr-auto-reviewer",
        "process-commands",
        "--repo",
        "forgejo:owner/repo",
        "--pr",
        "4",
    ])

    saved_pr = repository.find(pr_id)
    assert process_result == 0
    assert saved_pr is not None
    assert saved_pr.created_issue_item_ids == frozenset({suggestion.id})
    assert "Created 1 issue(s)" in comment_publisher.post_calls[0][1]
    assert saved_pr.latest_review_items()[0].status is ReviewItemStatus.CREATED
