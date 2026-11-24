from __future__ import annotations

import logging
from threading import Event, Thread
from unittest.mock import MagicMock, patch

import pytest

from pr_auto_reviewer.domain.entities.pull_request import PullRequest
from pr_auto_reviewer.domain.exceptions.repository_fetch_error import (
    RepositoryFetchError,
)
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

    def test_active_review_status_is_visible_while_review_is_running(self) -> None:
        state_port = MagicMock()
        entered = Event()
        release = Event()
        config = PollingDaemonConfig(
            poll_interval_seconds=300,
            repos_filter=None,
            run_once=True,
            repos_allow_list=("owner/repo",),
        )
        repo_lister = MagicMock()
        repo_lister.list_repos.return_value = []
        pr_lister = MagicMock()
        pr_lister.list_recent.return_value = []
        pr_lister.list_open.return_value = [
            OpenPullRequest(
                pr_id=PullRequestId("owner/repo", 42),
                head_sha=CommitSha("abc1234"),
                title="PR Title",
                description="PR Description",
            ),
        ]

        def execute(_command: object) -> ReviewExecutionResult:
            entered.set()
            assert release.wait(timeout=5)
            return ReviewExecutionResult(reviewed=True, duration_seconds=1.0)

        review_service = MagicMock()
        review_service.execute.side_effect = execute
        daemon = PollingDaemon(
            config,
            repo_lister,
            pr_lister,
            review_service,
            runtime_state=state_port,
        )
        worker = Thread(target=daemon.start)
        worker.start()

        assert entered.wait(timeout=5)
        statuses = [call.args[0] for call in state_port.record_status.call_args_list]
        reviewing = [status for status in statuses if status.state == DaemonState.REVIEWING]
        assert reviewing
        assert reviewing[-1].current_review is not None
        assert reviewing[-1].current_review.pr_number == 42
        assert reviewing[-1].current_cycle == 1

        release.set()
        worker.join(timeout=5)
        assert not worker.is_alive()

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

    def test_daemon_refreshes_allow_list_at_start_of_each_interaction(self) -> None:
        state_port = MagicMock()
        reloader = MagicMock()
        reloader.check_for_reload.return_value = Config(
            env="production",
            poll_interval=240,
            repos_allow_list=("new/repo",),
        )
        config = PollingDaemonConfig(
            poll_interval_seconds=300,
            repos_filter=None,
            run_once=True,
            repos_allow_list=("old/repo",),
        )
        repo_lister = MagicMock()
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

        daemon._run_cycle()

        assert reloader.check_for_reload.called
        status = state_port.record_status.call_args[0][0]
        assert status.allowed_repositories == ("new/repo",)

    def test_daemon_reads_settings_at_the_start_of_each_loop(self) -> None:
        state_port = MagicMock()
        reloader = MagicMock()
        reloader.check_for_reload.side_effect = [
            Config(env="production", poll_interval=120),
            Config(env="production", poll_interval=240),
        ]
        config = PollingDaemonConfig(
            poll_interval_seconds=300,
            repos_filter=None,
            run_once=False,
            repos_allow_list=(),
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
        with patch("time.sleep", side_effect=[None, KeyboardInterrupt]):
            daemon.start()

        assert reloader.check_for_reload.call_count == 2
        statuses = [call[0][0] for call in state_port.record_status.call_args_list]
        assert any(status.poll_interval_seconds == 240 for status in statuses)

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
        idle = [s for s in statuses if s.state == DaemonState.IDLE]
        assert idle
        assert idle[-1].current_review is None

    def test_failed_cycle_records_error_while_waiting_for_retry(self) -> None:
        state_port = MagicMock()
        config = PollingDaemonConfig(
            poll_interval_seconds=300,
            repos_filter=None,
            run_once=False,
            repos_allow_list=("forgejo:owner/repo",),
        )
        repo_lister = MagicMock()
        repo_lister.list_repos.return_value = []
        pr_lister = MagicMock()
        pr_lister.list_recent.return_value = []
        pr_lister.list_open.return_value = [
            OpenPullRequest(
                pr_id=PullRequestId("forgejo:owner/repo", 42),
                head_sha=CommitSha("abc1234"),
                title="PR Title",
                description="PR Description",
            ),
        ]
        review_service = MagicMock()
        review_service.execute.side_effect = RepositoryFetchError(
            "repository fetch failed"
        )
        daemon = PollingDaemon(
            config,
            repo_lister,
            pr_lister,
            review_service,
            runtime_state=state_port,
        )
        sleep_entered = Event()
        release_sleep = Event()

        def wait_for_next_cycle(_interval: int) -> None:
            sleep_entered.set()
            assert release_sleep.wait(timeout=5)
            raise KeyboardInterrupt

        worker = Thread(target=daemon.start)
        with patch(
            "pr_auto_reviewer.presentation.polling_daemon.polling_daemon.time.sleep",
            side_effect=wait_for_next_cycle,
        ):
            worker.start()
            try:
                assert sleep_entered.wait(timeout=5)
                assert worker.is_alive()
                statuses = [
                    call.args[0]
                    for call in state_port.record_status.call_args_list
                ]
                errors = [
                    status
                    for status in statuses
                    if status.state == DaemonState.ERROR
                ]
                assert errors
                error_status = errors[-1]
                assert "repository fetch failed" in (error_status.last_error or "")
                assert error_status.current_review is None
                assert error_status.next_cycle_at is not None
            finally:
                release_sleep.set()
                worker.join(timeout=5)

        assert not worker.is_alive()

    def test_logs_skip_reason_for_non_actionable_pr(self, caplog) -> None:
        repository = "forgejo:owner/repo"
        pr_id = PullRequestId(repository, 42)
        head_sha = CommitSha("abc1234")
        open_pr = OpenPullRequest(
            pr_id=pr_id,
            head_sha=head_sha,
            title="PR Title",
        )
        stored = PullRequest(
            id=pr_id,
            title="PR Title",
            head_sha=head_sha,
            reviews=(MagicMock(),),
        )
        state_tracker = MagicMock()
        state_tracker.is_stale.return_value = False
        pr_repository = MagicMock()
        pr_repository.find.return_value = stored
        config = PollingDaemonConfig(
            poll_interval_seconds=300,
            repos_filter=None,
            run_once=True,
        )
        repo_lister = MagicMock()
        repo_lister.list_repos.return_value = [
            RepoInfo(repository, pushed_at="same"),
        ]
        pr_lister = MagicMock()
        pr_lister.list_recent.return_value = []
        pr_lister.list_open.return_value = [open_pr]
        review_service = MagicMock()
        daemon = PollingDaemon(
            config,
            repo_lister,
            pr_lister,
            review_service,
            update_tracker=state_tracker,
            pr_repository=pr_repository,
        )

        caplog.set_level(
            logging.DEBUG,
            logger="pr_auto_reviewer.presentation.polling_daemon.polling_daemon",
        )
        daemon._run_cycle()

        assert not review_service.execute.called
        assert any(
            repository in record.message
            and "no new head" in record.message
            and "review-request event" in record.message
            and "dismissed platform review" in record.message
            and "force trigger" in record.message
            for record in caplog.records
        )

    @pytest.mark.parametrize(
        ("error", "expected_message"),
        [
            (RepositoryFetchError(), "RepositoryFetchError"),
            (RuntimeError(), "RuntimeError"),
        ],
    )
    def test_empty_exception_text_records_error_status(
        self,
        error: Exception,
        expected_message: str,
    ) -> None:
        state_port = MagicMock()
        config = PollingDaemonConfig(
            poll_interval_seconds=300,
            repos_filter=None,
            run_once=True,
            repos_allow_list=("owner/repo",),
        )
        repo_lister = MagicMock()
        pr_lister = MagicMock()
        review_service = MagicMock()
        review_service.execute.side_effect = error
        daemon = PollingDaemon(
            config,
            repo_lister,
            pr_lister,
            review_service,
            runtime_state=state_port,
        )

        daemon._process_pr(
            OpenPullRequest(
                pr_id=PullRequestId("owner/repo", 42),
                head_sha=CommitSha("abc1234"),
                title="PR Title",
            )
        )

        statuses = [call.args[0] for call in state_port.record_status.call_args_list]
        error_status = statuses[-1]
        assert error_status.state == DaemonState.ERROR
        assert error_status.last_error == expected_message
        assert error_status.current_review is None

    def test_logs_platform_qualified_identity_for_unqualified_pr(
        self,
        caplog,
    ) -> None:
        repository = "owner/repo"
        pr_id = PullRequestId(repository, 42)
        head_sha = CommitSha("abc1234")
        open_pr = OpenPullRequest(
            pr_id=pr_id,
            head_sha=head_sha,
            title="PR Title",
        )
        stored = PullRequest(
            id=pr_id,
            title="PR Title",
            head_sha=head_sha,
            reviews=(MagicMock(),),
        )
        state_tracker = MagicMock()
        state_tracker.is_stale.return_value = False
        pr_repository = MagicMock()
        pr_repository.find.return_value = stored
        config = PollingDaemonConfig(
            poll_interval_seconds=300,
            repos_filter=None,
            run_once=True,
            platforms=("forgejo",),
        )
        repo_lister = MagicMock()
        repo_lister.list_repos.return_value = [
            RepoInfo(repository, pushed_at="same"),
        ]
        pr_lister = MagicMock()
        pr_lister.list_recent.return_value = []
        pr_lister.list_open.return_value = [open_pr]
        review_service = MagicMock()
        daemon = PollingDaemon(
            config,
            repo_lister,
            pr_lister,
            review_service,
            update_tracker=state_tracker,
            pr_repository=pr_repository,
        )

        caplog.set_level(
            logging.DEBUG,
            logger="pr_auto_reviewer.presentation.polling_daemon.polling_daemon",
        )
        daemon._run_cycle()

        assert any(
            "forgejo:owner/repo#42" in record.message
            and "no new head" in record.message
            for record in caplog.records
        )
