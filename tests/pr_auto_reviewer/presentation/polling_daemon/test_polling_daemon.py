"""Tests for PollingDaemon."""

import logging
import signal
import threading
from unittest.mock import MagicMock, patch

import pytest

from pr_auto_reviewer.application.ports.inbound.process_issue_commands_port import (
    ProcessIssueCommandsPort,
)
from pr_auto_reviewer.application.ports.inbound.review_pull_request_port import (
    ReviewPullRequestPort,
)
from pr_auto_reviewer.application.ports.outbound.pull_request_repository_port import (
    PullRequestRepositoryPort,
)
from pr_auto_reviewer.domain.entities.pull_request import PullRequest
from pr_auto_reviewer.domain.messages.commands.process_issue_commands_command import (
    ProcessIssueCommandsCommand,
)
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.polling_daemon import (
    PollingDaemon,
    PollingDaemonConfig,
)
from pr_auto_reviewer.presentation.ports import (
    OpenPullRequest,
    PrListerPort,
    RepoInfo,
    RepoListerPort,
)
from tests.fakes.fake_notifier import FakeNotifier


class RecordingCommandService(ProcessIssueCommandsPort):
    """Records command scans dispatched by the daemon."""

    def __init__(self) -> None:
        self.commands: list[ProcessIssueCommandsCommand] = []

    def execute(self, command: ProcessIssueCommandsCommand) -> None:
        self.commands.append(command)


class PullRequestRepositoryFake(PullRequestRepositoryPort):
    """Stores one pull request aggregate for daemon tests."""

    def __init__(self, pull_request: PullRequest) -> None:
        self.pull_request = pull_request

    def find(self, pr_id: PullRequestId) -> PullRequest | None:
        if pr_id == self.pull_request.id:
            return self.pull_request
        return None

    def save(self, pr: PullRequest) -> None:
        self.pull_request = pr

    def reset(self) -> None:
        self.pull_request = PullRequest(
            id=self.pull_request.id,
            title=self.pull_request.title,
            head_sha=self.pull_request.head_sha,
        )


class MockRepoLister(RepoListerPort):
    def __init__(self, repos: list[RepoInfo]) -> None:
        self._repos = repos
        self.list_calls = 0

    def list_repos(self) -> list[RepoInfo]:
        self.list_calls += 1
        return self._repos

class MockPrLister(PrListerPort):
    def __init__(
        self,
        prs: list[OpenPullRequest],
        recent_prs: list[OpenPullRequest] | None = None,
    ) -> None:
        self._prs = prs
        self._recent_prs = recent_prs or []

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        return self._prs

    def list_recent(
        self, repository: str, since: str
    ) -> list[OpenPullRequest]:
        return self._recent_prs

    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
        for p in self._prs:
            if p.pr_id.number == pr_number:
                return p
        return None


class RecordingReviewService(ReviewPullRequestPort):
    def __init__(self) -> None:
        self.executed_commands: list[ReviewPullRequestCommand] = []

    def execute(self, command: ReviewPullRequestCommand) -> bool:
        self.executed_commands.append(command)
        return True

class PerRepoPrLister(PrListerPort):
    def list_open(self, repository: str) -> list[OpenPullRequest]:
        return [
            OpenPullRequest(
                pr_id=PullRequestId(repository=repository, number=1),
                head_sha=CommitSha("abc1234"),
                title="Fix bug",
                is_draft=False,
            )
        ]

    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
        return None

class TestPollingDaemon:
    """Tests for PollingDaemon class."""

    @pytest.fixture
    def config(self) -> PollingDaemonConfig:
        return PollingDaemonConfig(
            poll_interval_seconds=1,
            repos_filter=None,
            run_once=True,
        )

    @pytest.fixture
    def mock_review_service(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def daemon(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> PollingDaemon:
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        pr_lister = MockPrLister([])
        return PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )
    def test_continuous_mode_runs_next_cycle_after_first_sleep(
        self, mock_review_service: MagicMock
    ) -> None:
        config = PollingDaemonConfig(
            poll_interval_seconds=1,
            repos_filter=None,
            run_once=False,
        )
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=MockPrLister([]),
            review_service=mock_review_service,
        )

        with (
            patch(
                "pr_auto_reviewer.presentation.polling_daemon.polling_daemon.time.sleep",
                side_effect=[None, KeyboardInterrupt],
            ),
            patch(
                "pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger"
            ) as mock_logger,
        ):
            daemon.start()

        assert repo_lister.list_calls == 2
        mock_logger.info.assert_any_call("PollingDaemon stopped after 2 cycle(s)")

    def test_one_shot_mode_runs_exactly_one_cycle(
        self, mock_review_service: MagicMock
    ) -> None:
        config = PollingDaemonConfig(
            poll_interval_seconds=1,
            repos_filter=None,
            run_once=True,
        )
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=MockPrLister([]),
            review_service=mock_review_service,
        )

        with (
            patch(
                "pr_auto_reviewer.presentation.polling_daemon.polling_daemon.time.sleep"
            ) as mock_sleep,
            patch(
                "pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger"
            ) as mock_logger,
        ):
            daemon.start()

        assert repo_lister.list_calls == 1
        mock_sleep.assert_not_called()
        mock_logger.info.assert_any_call("PollingDaemon stopped after 1 cycle(s)")


    def test_does_not_notify_success_when_review_is_skipped(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        mock_review_service.execute.return_value = False
        pull_request = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=7),
            head_sha=CommitSha("abc123"),
            title="Already reviewed fix",
        )
        notifier = FakeNotifier()
        daemon = PollingDaemon(
            config=config,
            repo_lister=MockRepoLister([]),
            pr_lister=MockPrLister([]),
            review_service=mock_review_service,
            notifier=notifier,
        )

        daemon._process_pr(pull_request)

        assert notifier.successes == []

    def test_notifies_success_after_review_completion(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        mock_review_service.execute.return_value = True
        pr_id = PullRequestId(repository="owner/repo1", number=7)
        pull_request = OpenPullRequest(
            pr_id=pr_id,
            head_sha=CommitSha("abc123"),
            title="Completed fix",
        )
        notifier = FakeNotifier()
        daemon = PollingDaemon(
            config=config,
            repo_lister=MockRepoLister([]),
            pr_lister=MockPrLister([]),
            review_service=mock_review_service,
            notifier=notifier,
        )

        daemon._process_pr(pull_request)

        assert len(notifier.successes) == 1
        context, detail = notifier.successes[0]
        assert context.startswith("Review complete for owner/repo1 (")
        assert context.endswith(")")
        assert detail == "PR #7"

    def test_processes_recent_closed_pr_commands(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        """Processes commands for a recently closed pull request."""
        pr_id = PullRequestId(repository="owner/repo1", number=7)
        recent_pr = OpenPullRequest(
            pr_id=pr_id,
            head_sha=CommitSha("abc123"),
            title="Closed fix",
            updated_at="2026-09-11T01:00:00Z",
        )
        stored = PullRequest(
            id=pr_id,
            title=recent_pr.title,
            head_sha=recent_pr.head_sha,
        )
        command_service = RecordingCommandService()
        daemon = PollingDaemon(
            config=config,
            repo_lister=MockRepoLister([RepoInfo("owner/repo1")]),
            pr_lister=MockPrLister([], [recent_pr]),
            review_service=mock_review_service,
            process_commands_service=command_service,
            pr_repository=PullRequestRepositoryFake(stored),
        )

        daemon.start()

        assert [command.pr_id for command in command_service.commands] == [pr_id]

    def test_does_not_repeat_command_scan_until_pr_activity_changes(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        """Scans comments once for each pull request activity timestamp."""
        pr_id = PullRequestId(repository="owner/repo1", number=7)
        recent_pr = OpenPullRequest(
            pr_id=pr_id,
            head_sha=CommitSha("abc123"),
            title="Closed fix",
            updated_at="2026-09-11T01:00:00Z",
        )
        repository = PullRequestRepositoryFake(
            PullRequest(id=pr_id, title=recent_pr.title, head_sha=recent_pr.head_sha)
        )
        command_service = RecordingCommandService()
        pr_lister = MockPrLister([], [recent_pr])
        daemon = PollingDaemon(
            config=config,
            repo_lister=MockRepoLister([RepoInfo("owner/repo1")]),
            pr_lister=pr_lister,
            review_service=mock_review_service,
            process_commands_service=command_service,
            pr_repository=repository,
        )

        daemon._run_cycle()
        daemon._run_cycle()
        pr_lister._recent_prs = [
            OpenPullRequest(
                pr_id=pr_id,
                head_sha=recent_pr.head_sha,
                title=recent_pr.title,
                updated_at="2026-09-11T02:00:00Z",
            )
        ]
        daemon._run_cycle()

        assert len(command_service.commands) == 2

    def test_creation(self, daemon: PollingDaemon) -> None:
        """Creates PollingDaemon with all dependencies."""
        assert daemon is not None

    def test_no_repos(self, config: PollingDaemonConfig, mock_review_service: MagicMock) -> None:
        """Logs warning when no repos found."""
        repo_lister = MockRepoLister([])
        pr_lister = MockPrLister([])
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

        with patch("pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger") as mock_logger:
            daemon.start()
            mock_logger.warning.assert_called_once_with("No repositories found")

    def test_no_prs_does_not_log_repository_details(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        """Does not log a message for each repository without open PRs."""
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        pr_lister = MockPrLister([])
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

        with patch("pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger") as mock_logger:
            daemon.start()
            mock_logger.debug.assert_not_called()

    def test_skips_draft_prs(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        """Skips draft PRs."""
        draft_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=1),
            head_sha=CommitSha("abc123"),
            title="WIP",
            is_draft=True,
        )
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        pr_lister = MockPrLister([draft_pr])
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

        with patch("pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger") as mock_logger:
            daemon.start()
            mock_logger.debug.assert_called_with("Skipping draft PR #1")

        mock_review_service.execute.assert_not_called()

    def test_processes_open_pr(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        """Processes open (non-draft) PRs."""
        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        pr_lister = MockPrLister([open_pr])
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

        with patch("pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger") as mock_logger:
            daemon.start()
            mock_logger.info.assert_any_call(
                "Reviewed PR #%d in %s", 1, "owner/repo1"
            )

        mock_review_service.execute.assert_called_once()

    def test_force_pr_passes_force_flag(
        self, mock_review_service: MagicMock
    ) -> None:
        """force_pr config sets force=True on the command."""
        config = PollingDaemonConfig(
            poll_interval_seconds=1,
            repos_filter=None,
            run_once=True,
            force_pr=1,
        )
        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        pr_lister = MockPrLister([open_pr])
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

        with patch(
            "pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger"
        ) as _mock_logger:
            daemon.start()

        mock_review_service.execute.assert_called_once()
        dispatched = mock_review_service.execute.call_args[0][0]
        assert dispatched.force is True
        assert dispatched.pr_id.number == 1


    def test_force_pr_mismatched_does_not_set_force(
        self, mock_review_service: MagicMock
    ) -> None:
        """force_pr only sets force=True for the matching PR number."""
        config = PollingDaemonConfig(
            poll_interval_seconds=1,
            repos_filter=None,
            run_once=True,
            force_pr=2,
        )
        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        pr_lister = MockPrLister([open_pr])
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

        with patch(
            "pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger"
        ) as mock_logger:
            daemon.start()

        mock_review_service.execute.assert_called_once()
        dispatched = mock_review_service.execute.call_args[0][0]
        assert dispatched.force is False
        force_calls = [
            c for c in mock_logger.info.call_args_list
            if "Force-reviewing" in str(c)
        ]
        assert len(force_calls) == 0

    def test_review_request_reaches_service_when_repo_push_timestamp_is_unchanged(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        pushed_at = "2026-09-11T00:00:00Z"
        tracker = MagicMock()
        tracker.is_stale.return_value = False
        repo_lister = MockRepoLister(
            [RepoInfo("owner/repo1", pushed_at=pushed_at)]
        )
        requested_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            review_requested=True,
        )
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=MockPrLister([requested_pr]),
            review_service=mock_review_service,
            update_tracker=tracker,
        )

        daemon.start()

        mock_review_service.execute.assert_called_once()
        dispatched = mock_review_service.execute.call_args.args[0]
        assert dispatched.review_requested is True

    def test_unchanged_repo_skips_open_pr_without_review_request(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        pushed_at = "2026-09-11T00:00:00Z"
        tracker = MagicMock()
        tracker.is_stale.return_value = False
        repo_lister = MockRepoLister(
            [RepoInfo("owner/repo1", pushed_at=pushed_at)]
        )
        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
        )
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=MockPrLister([open_pr]),
            review_service=mock_review_service,
            update_tracker=tracker,
        )

        daemon.start()

        mock_review_service.execute.assert_not_called()

    def test_handles_empty_diff_error(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        """Handles EmptyDiffError gracefully."""
        from pr_auto_reviewer.domain.exceptions.empty_diff_error import EmptyDiffError

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        pr_lister = MockPrLister([open_pr])
        mock_review_service.execute.side_effect = EmptyDiffError("empty")

        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

        with patch("pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger") as mock_logger:
            daemon.start()
            mock_logger.warning.assert_called_with("Empty diff, skipping PR #%d", 1)
            reviewed_calls = [
                c for c in mock_logger.info.call_args_list
                if "Reviewed PR #1" in str(c)
            ]
            assert len(reviewed_calls) == 0

    def test_handles_repository_fetch_error_gracefully(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        from pr_auto_reviewer.domain.exceptions.repository_fetch_error import (
            RepositoryFetchError,
        )

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        pr_lister = MockPrLister([open_pr])
        mock_review_service.execute.side_effect = RepositoryFetchError(
            "git@codeberg.org: Permission denied (publickey)."
        )

        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

        with patch("pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger") as mock_logger:
            daemon.start()
            fetch_warnings = [
                c for c in mock_logger.warning.call_args_list
                if "Could not fetch repository for PR #%d" in str(c)
                and "Permission denied" in str(c)
            ]
            assert len(fetch_warnings) == 1
            unexpected_calls = [
                c for c in mock_logger.exception.call_args_list
                if "Unexpected error processing PR #1" in str(c)
            ]
            assert len(unexpected_calls) == 0

    def test_repository_fetch_error_continues_to_next_pr(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        from pr_auto_reviewer.domain.exceptions.repository_fetch_error import (
            RepositoryFetchError,
        )

        first_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=1),
            head_sha=CommitSha("abc123"),
            title="First",
            is_draft=False,
        )
        second_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=2),
            head_sha=CommitSha("def456"),
            title="Second",
            is_draft=False,
        )
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        pr_lister = MockPrLister([first_pr, second_pr])
        mock_review_service.execute.side_effect = [
            RepositoryFetchError("host unreachable"),
            None,
        ]

        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

        with patch("pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger"):
            daemon.start()

        assert mock_review_service.execute.call_count == 2
        handled_numbers = [
            c.args[0].pr_id.number for c in mock_review_service.execute.call_args_list
        ]
        assert handled_numbers == [1, 2]

    def test_handles_review_verdict_error_gracefully(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        from pr_auto_reviewer.domain.exceptions.review_verdict_error import (
            ReviewVerdictError,
        )

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        pr_lister = MockPrLister([open_pr])
        mock_review_service.execute.side_effect = ReviewVerdictError(
            "Review remained inconclusive after 5 attempts."
        )

        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

        with patch("pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger") as mock_logger:
            daemon.start()
            inconclusive_warnings = [
                c for c in mock_logger.warning.call_args_list
                if "Review inconclusive for PR #%d" in str(c)
            ]
            assert len(inconclusive_warnings) == 1
            unexpected_calls = [
                c for c in mock_logger.exception.call_args_list
                if "Unexpected error processing PR #1" in str(c)
            ]
            assert len(unexpected_calls) == 0

    def test_signal_handler_raises_keyboard_interrupt(self, daemon):
        daemon._setup_signal_handlers()
        with pytest.raises(KeyboardInterrupt):
            signal.raise_signal(signal.SIGINT)

    def test_daemon_stops_on_keyboard_interrupt(self, daemon):
        with patch(
            "pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger"
        ) as mock_logger:
            daemon.start()
        mock_logger.info.assert_any_call("PollingDaemon stopped after 1 cycle(s)")

    def test_ctrl_c_stops_daemon_during_blocking_review(
        self, config, mock_review_service,
    ):
        mock_review_service.execute.side_effect = KeyboardInterrupt

        open_pr = OpenPullRequest(
            pr_id=PullRequestId(repository="owner/repo1", number=1),
            head_sha=CommitSha("abc123"),
            title="Fix bug",
            is_draft=False,
        )
        repo_lister = MockRepoLister([RepoInfo("owner/repo1")])
        pr_lister = MockPrLister([open_pr])
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

        daemon_thread = threading.Thread(target=daemon.start, daemon=True)
        daemon_thread.start()
        daemon_thread.join(timeout=2)
        assert not daemon_thread.is_alive()

    def test_keyboard_interrupt_preserves_stop_message(self, daemon):
        with patch(
            "pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger"
        ) as mock_logger:
            daemon.start()
        stopped_calls = [
            c for c in mock_logger.info.call_args_list
            if "PollingDaemon stopped after 1 cycle(s)" in str(c)
        ]
        assert len(stopped_calls) == 1

    def test_allow_list_avoids_repository_discovery(self) -> None:
        config = PollingDaemonConfig(
            poll_interval_seconds=1,
            repos_filter=None,
            run_once=True,
            repos_allow_list=("owner/allowed",),
        )
        repo_lister = MockRepoLister([])
        review_service = RecordingReviewService()
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=PerRepoPrLister(),
            review_service=review_service,
        )

        daemon.start()

        assert repo_lister.list_calls == 0
        assert [
            command.pr_id.repository
            for command in review_service.executed_commands
        ] == ["owner/allowed"]

    def test_reviews_only_allowed_repositories(self) -> None:
        config = PollingDaemonConfig(
            poll_interval_seconds=1,
            repos_filter=None,
            run_once=True,
            repos_allow_list=("owner/allowed",),
        )
        repo_lister = MockRepoLister(
            [RepoInfo("owner/allowed"), RepoInfo("owner/other")]
        )
        review_service = RecordingReviewService()
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=PerRepoPrLister(),
            review_service=review_service,
        )

        daemon.start()

        reviewed_repositories = [
            command.pr_id.repository
            for command in review_service.executed_commands
        ]
        assert reviewed_repositories == ["owner/allowed"]

    def test_allow_list_skips_are_debug_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        config = PollingDaemonConfig(
            poll_interval_seconds=1,
            repos_filter=None,
            run_once=True,
            repos_allow_list=("owner/allowed",),
        )
        daemon = PollingDaemon(
            config=config,
            repo_lister=MockRepoLister([]),
            pr_lister=PerRepoPrLister(),
            review_service=RecordingReviewService(),
        )
        repos = [RepoInfo("owner/allowed"), RepoInfo("owner/other")]

        with caplog.at_level(
            logging.INFO,
            logger="pr_auto_reviewer.presentation.polling_daemon.polling_daemon",
        ):
            daemon._allowed_repos(repos)


        assert not any(
            "Skipping repository not in allow list" in record.message
            for record in caplog.records
        )

        caplog.clear()
        with caplog.at_level(
            logging.DEBUG,
            logger="pr_auto_reviewer.presentation.polling_daemon.polling_daemon",
        ):
            daemon._allowed_repos(repos)

        debug_records = [
            record
            for record in caplog.records
            if record.levelno == logging.DEBUG
        ]
        assert len(debug_records) == 1
        assert debug_records[0].message == (
            "Skipping 1 repositories not in allow list"
        )


    def test_cycle_does_not_log_allow_list(self, caplog: pytest.LogCaptureFixture) -> None:
        config = PollingDaemonConfig(
            poll_interval_seconds=1,
            repos_filter=None,
            run_once=True,
            repos_allow_list=("owner/allowed",),
        )
        daemon = PollingDaemon(
            config=config,
            repo_lister=MockRepoLister([RepoInfo("owner/allowed")]),
            pr_lister=PerRepoPrLister(),
            review_service=RecordingReviewService(),
        )

        with caplog.at_level(logging.INFO):
            daemon._run_cycle()

        assert not any(
            "Repository allow list:" in record.message
            for record in caplog.records
        )

    def test_empty_allow_list_reviews_every_repository(self) -> None:
        config = PollingDaemonConfig(
            poll_interval_seconds=1,
            repos_filter=None,
            run_once=True,
            repos_allow_list=(),
        )
        repo_lister = MockRepoLister(
            [RepoInfo("owner/allowed"), RepoInfo("owner/other")]
        )
        review_service = RecordingReviewService()
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=PerRepoPrLister(),
            review_service=review_service,
        )

        daemon.start()

        reviewed_repositories = sorted(
            command.pr_id.repository
            for command in review_service.executed_commands
        )
        assert reviewed_repositories == ["owner/allowed", "owner/other"]

    def test_reviews_only_matching_platform_when_prefixed(self) -> None:
        config = PollingDaemonConfig(
            poll_interval_seconds=1,
            repos_filter=None,
            run_once=True,
            repos_allow_list=("github:owner/app",),
        )
        repo_lister = MockRepoLister(
            [RepoInfo("github:owner/app"), RepoInfo("forgejo:owner/app")]
        )
        review_service = RecordingReviewService()
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=PerRepoPrLister(),
            review_service=review_service,
        )

        daemon.start()

        reviewed_repositories = [
            command.pr_id.repository
            for command in review_service.executed_commands
        ]
        assert reviewed_repositories == ["github:owner/app"]
