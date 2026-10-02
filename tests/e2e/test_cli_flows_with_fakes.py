"""End-to-end CLI flow tests using in-repository fakes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from pr_auto_reviewer.domain.entities.pull_request import PullRequest
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.process_issue_commands_command import (
    ProcessIssueCommandsCommand,
)
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.cli.runner import CliRunner
from pr_auto_reviewer.presentation.ports import OpenPullRequest
from pr_auto_reviewer.presentation.ports.pr_lister_port import PrListerPort
from tests.fakes.fake_forgejo_pr_lister import FakeForgejoPrLister
from tests.fakes.fake_notifier import FakeNotifier
from tests.fakes.fake_pull_request_repository import FakePullRequestRepository


@dataclass
class FakeReviewService:
    """Record review commands accepted by the application boundary."""

    executed_commands: list[ReviewPullRequestCommand]

    def execute(self, command: ReviewPullRequestCommand) -> bool:
        """Accept a review command without external services."""
        self.executed_commands.append(command)
        return True


@dataclass
class FakeProcessCommandsService:
    """Record process-command requests accepted by the application boundary."""

    executed_commands: list[ProcessIssueCommandsCommand]

    def execute(self, command: ProcessIssueCommandsCommand) -> None:
        """Accept a process-command request without external services."""
        self.executed_commands.append(command)


class FakeReviewReader:
    """Return a configured published review body."""

    def __init__(self, body: str | None) -> None:
        self._body = body

    def get_latest_review(self, pr_id: PullRequestId) -> str | None:
        """Return the configured review body."""
        return self._body


class FakeReviewItemParser:
    """Return configured review items."""

    def __init__(self, items: list[ReviewItem]) -> None:
        self._items = items

    def parse(self, raw_body: str) -> list[ReviewItem]:
        """Return configured items for the supplied review body."""
        return list(self._items)


@pytest.fixture
def open_pull_request() -> OpenPullRequest:
    """Build the PR used by each CLI flow."""
    return OpenPullRequest(
        pr_id=PullRequestId(repository="forgejo:owner/repo", number=4),
        head_sha=CommitSha("abc123"),
        title="Test pull request",
        description="Test description",
        is_draft=False,
        review_requested=False,
        target_branch="main",
    )


@pytest.fixture
def cli_components(
    open_pull_request: OpenPullRequest,
) -> tuple[
    CliRunner,
    FakeForgejoPrLister,
    FakeReviewService,
    FakeProcessCommandsService,
    FakePullRequestRepository,
    FakeNotifier,
]:
    """Build the CLI runner with fake ports at every external boundary."""
    pr_lister = FakeForgejoPrLister([open_pull_request])
    review_service = FakeReviewService([])
    process_service = FakeProcessCommandsService([])
    repository = FakePullRequestRepository()
    notifier = FakeNotifier()
    review_item_parser = FakeReviewItemParser([
        ReviewItem(
            id="a1b2c3",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="src/app.py",
            description="Handle the error path",
        )
    ])
    runner = CliRunner(
        review_service=review_service,
        process_commands_service=process_service,
        review_reader=FakeReviewReader("review body"),
        pr_lister=cast(PrListerPort, pr_lister),
        review_item_parser=cast(ReviewItemParser, review_item_parser),
        pr_repository=repository,
        notifier=notifier,
        output_mode="forgejo",
    )
    return runner, pr_lister, review_service, process_service, repository, notifier


@pytest.mark.e2e
class TestCliFlowsWithFakes:
    """Exercise CLI command flows through real presentation code and fakes."""

    def test_review_command_executes_review_for_selected_pr(
        self,
        cli_components: tuple[
            CliRunner,
            FakeForgejoPrLister,
            FakeReviewService,
            FakeProcessCommandsService,
            FakePullRequestRepository,
            FakeNotifier,
        ],
    ) -> None:
        """A review command forwards the selected PR and reports success."""
        runner, pr_lister, review_service, _, _, notifier = cli_components

        result = runner.run([
            "pr-auto-reviewer", "review", "--repo", "forgejo:owner/repo",
            "--pr", "4", "--force",
        ])

        assert result == 0
        assert pr_lister.get_pr_calls == [("forgejo:owner/repo", 4)]
        assert [command.pr_id for command in review_service.executed_commands] == [
            PullRequestId(repository="forgejo:owner/repo", number=4)
        ]
        assert notifier.errors == []

    def test_process_commands_executes_for_selected_pr(
        self,
        cli_components: tuple[
            CliRunner,
            FakeForgejoPrLister,
            FakeReviewService,
            FakeProcessCommandsService,
            FakePullRequestRepository,
            FakeNotifier,
        ],
    ) -> None:
        """A process-commands request uses the selected PR number and SHA."""
        runner, pr_lister, _, process_service, _, _ = cli_components

        result = runner.run([
            "pr-auto-reviewer", "process-commands", "--repo",
            "forgejo:owner/repo", "--pr", "4",
        ])

        assert result == 0
        assert pr_lister.list_open_calls == ["forgejo:owner/repo"]
        assert process_service.executed_commands == [
            ProcessIssueCommandsCommand(
                pr_id=PullRequestId(repository="forgejo:owner/repo", number=4),
                head_sha=CommitSha("abc123"),
            )
        ]

    def test_list_items_displays_parsed_review_items(
        self,
        cli_components: tuple[
            CliRunner,
            FakeForgejoPrLister,
            FakeReviewService,
            FakeProcessCommandsService,
            FakePullRequestRepository,
            FakeNotifier,
        ],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A list-items request displays items returned by the parser port."""
        runner, _, _, _, _, _ = cli_components

        result = runner.run([
            "pr-auto-reviewer", "list-items", "--repo",
            "forgejo:owner/repo", "--pr", "4",
        ])

        output = capsys.readouterr().out
        assert result == 0
        assert "a1b2c3" in output
        assert "Handle the error path" in output

    def test_clean_resets_persisted_state(
        self,
        cli_components: tuple[
            CliRunner,
            FakeForgejoPrLister,
            FakeReviewService,
            FakeProcessCommandsService,
            FakePullRequestRepository,
            FakeNotifier,
        ],
    ) -> None:
        """A clean request resets the injected repository port."""
        runner, _, _, _, repository, _ = cli_components
        repository.save(
            PullRequest(
                id=PullRequestId(repository="forgejo:owner/repo", number=4),
                title="Test pull request",
                head_sha=CommitSha("abc123"),
            )
        )

        result = runner.run(["pr-auto-reviewer", "clean"])

        assert result == 0
        assert repository.reset_calls == 1
        assert repository.find(
            PullRequestId(repository="forgejo:owner/repo", number=4)
        ) is None
