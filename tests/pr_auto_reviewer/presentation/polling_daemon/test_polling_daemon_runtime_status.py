from __future__ import annotations

from unittest.mock import MagicMock, patch

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_execution_result import (
    ReviewExecutionResult,
)
from pr_auto_reviewer.infrastructure.config.config_dataclass import Config
from pr_auto_reviewer.presentation.polling_daemon import (
    PollingDaemon,
    PollingDaemonConfig,
)
from pr_auto_reviewer.presentation.ports import (
    OpenPullRequest,
    RepoInfo,
)


class TestPollingDaemonRuntimeStatus:
    """Verifies PollingDaemon writes runtime status and handles config reload."""

    def test_daemon_records_idle_and_stopped_status(self) -> None:
        state_port = MagicMock()
        config = PollingDaemonConfig(
            poll_interval_seconds=300,
            repos_filter=None,
            run_once=False,
            repos_allow_list=("owner/repo",),
        )
        repo_lister = MagicMock()
        pr_lister = MagicMock()
        pr_lister.list_recent.return_value = []
        pr_lister.list_open.return_value = []
        review_service = MagicMock()

        daemon = PollingDaemon(
            config,
            repo_lister,
            pr_lister,
            review_service,
            runtime_state=state_port,
        )
        with patch("time.sleep", side_effect=KeyboardInterrupt):
            daemon.start()

        assert state_port.record_status.called
        recorded = state_port.record_status.call_args_list[0][0][0]
        assert recorded.daemon_mode is True
        assert recorded.poll_interval_seconds == 300
        assert recorded.allowed_repositories == ("owner/repo",)

    def test_daemon_reloads_config_when_sha_changes(self) -> None:
        state_port = MagicMock()
        reloader = MagicMock()
        new_config = Config(
            env="production",
            poll_interval=120,
            repos_allow_list=("new/repo",),
        )
        reloader.check_for_reload.return_value = new_config
        config = PollingDaemonConfig(
            poll_interval_seconds=300,
            repos_filter=None,
            run_once=True,
            repos_allow_list=("old/repo",),
        )
        repo_lister = MagicMock()
        repo_lister.list_repos.return_value = []
        pr_lister = MagicMock()
        review_service = MagicMock()

        daemon = PollingDaemon(
            config,
            repo_lister,
            pr_lister,
            review_service,
            runtime_state=state_port,
            config_reloader=reloader,
        )
        daemon.start()

        statuses = [
            call[0][0] for call in state_port.record_status.call_args_list
        ]
        reloaded = [
            s for s in statuses if s.poll_interval_seconds == 120
        ]
        assert reloader.check_for_reload.called
        assert len(reloaded) >= 1
        assert reloaded[0].allowed_repositories == ("new/repo",)

    def test_daemon_records_reviewing_status_during_pr_processing(self) -> None:
        state_port = MagicMock()
        config = PollingDaemonConfig(
            poll_interval_seconds=300,
            repos_filter=None,
            run_once=True,
            repos_allow_list=("owner/repo",),
        )
        repo_lister = MagicMock()
        repo_lister.list_repos.return_value = [
            RepoInfo("owner/repo", "2026-11-09T18:00:00Z"),
        ]
        pr_lister = MagicMock()
        pr_lister.list_recent.return_value = []
        pr_lister.list_open.return_value = [
            OpenPullRequest(
                pr_id=PullRequestId("owner/repo", 42),
                head_sha=CommitSha("abc1234"),
                title="PR Title",
                description="PR Description",
                review_requested=True,
            ),
        ]
        review_service = MagicMock()
        review_service.execute.return_value = ReviewExecutionResult(
            reviewed=True, duration_seconds=10.0,
        )

        daemon = PollingDaemon(
            config,
            repo_lister,
            pr_lister,
            review_service,
            runtime_state=state_port,
        )
        daemon.start()

        statuses = [call[0][0] for call in state_port.record_status.call_args_list]
        reviewing = [s for s in statuses if s.state == DaemonState.REVIEWING]
        assert len(reviewing) >= 1
        assert reviewing[0].current_review is not None
        assert reviewing[0].current_review.repository == "owner/repo"
        assert reviewing[0].current_review.pr_number == 42
