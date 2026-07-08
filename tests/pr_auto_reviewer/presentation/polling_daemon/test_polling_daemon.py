"""Tests for PollingDaemon."""

import signal
import threading
from unittest.mock import MagicMock, patch

import pytest

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.ports import OpenPullRequest, RepoListerPort, PrListerPort
from pr_auto_reviewer.presentation.polling_daemon import PollingDaemon, PollingDaemonConfig

class MockRepoLister(RepoListerPort):
    def __init__(self, repos: list[str]) -> None:
        self._repos = repos

    def list_repos(self) -> list[str]:
        return self._repos

class MockPrLister(PrListerPort):
    def __init__(self, prs: list[OpenPullRequest]) -> None:
        self._prs = prs

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        return self._prs

    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
        for p in self._prs:
            if p.pr_id.number == pr_number:
                return p
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
        repo_lister = MockRepoLister(["owner/repo1"])
        pr_lister = MockPrLister([])
        return PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

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

    def test_no_prs(
        self, config: PollingDaemonConfig, mock_review_service: MagicMock
    ) -> None:
        """Logs debug when no open PRs in repo."""
        repo_lister = MockRepoLister(["owner/repo1"])
        pr_lister = MockPrLister([])
        daemon = PollingDaemon(
            config=config,
            repo_lister=repo_lister,
            pr_lister=pr_lister,
            review_service=mock_review_service,
        )

        with patch("pr_auto_reviewer.presentation.polling_daemon.polling_daemon.logger") as mock_logger:
            daemon.start()
            mock_logger.debug.assert_called_with("No open PRs in owner/repo1")

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
        repo_lister = MockRepoLister(["owner/repo1"])
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
        repo_lister = MockRepoLister(["owner/repo1"])
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
        repo_lister = MockRepoLister(["owner/repo1"])
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
        repo_lister = MockRepoLister(["owner/repo1"])
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
        repo_lister = MockRepoLister(["owner/repo1"])
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
        repo_lister = MockRepoLister(["owner/repo1"])
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
