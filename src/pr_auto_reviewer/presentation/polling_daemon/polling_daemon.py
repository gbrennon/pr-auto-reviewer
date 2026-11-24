"""PollingDaemon - polls repositories for open PRs and triggers reviews."""

from __future__ import annotations

import logging
import os
import signal
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from pr_auto_reviewer.application.ports.inbound.process_issue_commands_port import (
    ProcessIssueCommandsPort,
)
from pr_auto_reviewer.application.ports.inbound.review_pull_request_port import (
    ReviewPullRequestPort,
)
from pr_auto_reviewer.application.ports.outbound.daemon_runtime_state_port import (
    DaemonRuntimeStatePort,
)
from pr_auto_reviewer.application.ports.outbound.notifier_port import NotifierPort
from pr_auto_reviewer.application.ports.outbound.pull_request_repository_port import (
    PullRequestRepositoryPort,
)
from pr_auto_reviewer.application.services.pr_identifier_service import (
    PRIdentifierService,
)
from pr_auto_reviewer.domain.entities.pull_request import PullRequest
from pr_auto_reviewer.domain.exceptions.empty_diff_error import EmptyDiffError
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.exceptions.repository_fetch_error import (
    RepositoryFetchError,
)
from pr_auto_reviewer.domain.exceptions.remote_operation_quarantined_error import (
    RemoteOperationQuarantinedError,
)
from pr_auto_reviewer.domain.exceptions.review_publish_error import ReviewPublishError
from pr_auto_reviewer.domain.exceptions.review_verdict_error import (
    ReviewVerdictError,
)
from pr_auto_reviewer.domain.messages.commands.process_issue_commands_command import (
    ProcessIssueCommandsCommand,
)
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.services.repository_allow_list import (
    RepositoryAllowList,
)
from pr_auto_reviewer.domain.value_objects.active_review_progress import (
    ActiveReviewProgress,
)
from pr_auto_reviewer.domain.value_objects.daemon_runtime_status import (
    DaemonRuntimeStatus,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState
from pr_auto_reviewer.infrastructure.client.http_request_counter import (
    HttpRequestCounter,
)
from pr_auto_reviewer.infrastructure.client.remote_host_backoff import (
    RemoteHostBackoff,
)
from pr_auto_reviewer.infrastructure.client.repo_update_tracker import RepoUpdateTracker
from pr_auto_reviewer.infrastructure.temp_file_cleaner import clean_temp_files
from pr_auto_reviewer.presentation.polling_daemon.polling_daemon_config import (
    PollingDaemonConfig,
)
from pr_auto_reviewer.presentation.ports import (
    OpenPullRequest,
    PrListerPort,
    RepoInfo,
    RepoListerPort,
)
from pr_auto_reviewer.presentation.ports.config_reloader_port import (
    ConfigReloaderPort,
)

logger = logging.getLogger(__name__)
COMMAND_LOOKBACK_DAYS = 7
_LLM_FAILURE_COOLDOWN_SECONDS = 300


class PollingDaemon:

    def __init__(
        self,
        config: PollingDaemonConfig,
        repo_lister: RepoListerPort,
        pr_lister: PrListerPort,
        review_service: ReviewPullRequestPort,
        *,
        notifier: NotifierPort | None = None,
        update_tracker: RepoUpdateTracker | None = None,
        repository_allow_list: RepositoryAllowList | None = None,
        process_commands_service: ProcessIssueCommandsPort | None = None,
        pr_repository: PullRequestRepositoryPort | None = None,
        runtime_state: DaemonRuntimeStatePort | None = None,
        config_reloader: ConfigReloaderPort | None = None,
        command_failure_backoff: RemoteHostBackoff | None = None,
    ) -> None:
        self._config = config
        self._repo_lister = repo_lister
        self._pr_lister = pr_lister
        self._review_service = review_service
        self._notifier = notifier
        self._update_tracker = update_tracker
        self._repository_allow_list = (
            repository_allow_list
            if repository_allow_list is not None
            else RepositoryAllowList.from_entries(config.repos_allow_list)
        )
        self._process_commands_service = process_commands_service
        self._pr_repository = pr_repository
        self._runtime_state = runtime_state
        self._config_reloader = config_reloader
        self._command_failure_backoff = (
            command_failure_backoff
            if command_failure_backoff is not None
            else RemoteHostBackoff()
        )
        self._force_pr = getattr(config, "force_pr", None)
        self._llm_retry_at = 0.0
        self._current_cycle = 0
        self._cycle_error: str | None = None
        self._setup_signal_handlers()

    def start(self) -> None:
        """Start the polling loop."""
        logger.info(
            f"Starting PollingDaemon (interval={self._config.poll_interval_seconds}s, "
            f"run_once={self._config.run_once})"
        )
        try:
            deleted = clean_temp_files()
            if deleted:
                logger.info("Cleaned up %d stale temp file(s)", deleted)
        except Exception:
            logger.warning("Temp file cleanup failed, continuing", exc_info=True)

        cycle = 0
        self._record_runtime_status(DaemonState.IDLE, cycle=0)
        try:
            while True:
                cycle += 1
                self._current_cycle = cycle
                self._run_cycle()

                if self._config.run_once:
                    break

                interval = self._config.poll_interval_seconds
                next_at = (datetime.now(UTC) + timedelta(seconds=interval)).isoformat()
                cycle_error = self._cycle_error
                self._record_runtime_status(
                    DaemonState.ERROR if cycle_error is not None else DaemonState.IDLE,
                    next_cycle_at=next_at,
                    cycle=cycle,
                    error=cycle_error,
                )
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
        finally:
            self._record_runtime_status(DaemonState.STOPPED, cycle=cycle)

        logger.info(f"PollingDaemon stopped after {cycle} cycle(s)")

    def _check_config_reload(self) -> None:
        if self._config_reloader is None:
            return
        new_config = self._config_reloader.check_for_reload()
        new_daemon_config = replace(
            self._config,
            poll_interval_seconds=new_config.poll_interval,
            repos_allow_list=new_config.repos_allow_list,
            repos_filter=new_config.repos_filter or None,
        )
        holder = self.__dict__
        holder["_config"] = new_daemon_config
        holder["_repository_allow_list"] = RepositoryAllowList.from_entries(
            new_config.repos_allow_list
        )
        self._record_runtime_status(DaemonState.IDLE)

    def _record_runtime_status(
        self,
        state: DaemonState,
        *,
        current_review: ActiveReviewProgress | None = None,
        next_cycle_at: str | None = None,
        cycle: int = 0,
        error: str | None = None,
    ) -> None:
        if self._runtime_state is None:
            return
        now_str = datetime.now(UTC).isoformat()
        status = DaemonRuntimeStatus(
            pid=os.getpid(),
            daemon_mode=not self._config.run_once,
            state=state,
            updated_at=now_str,
            poll_interval_seconds=self._config.poll_interval_seconds,
            allowed_repositories=self._config.repos_allow_list,
            current_cycle=cycle or self._current_cycle,
            next_cycle_at=next_cycle_at,
            current_review=current_review,
            last_error=error,
            last_error_at=now_str if error else None,
        )
        self._runtime_state.record_status(status)

    def _setup_signal_handlers(self) -> None:
        def handle_signal(signum: int, frame: object) -> None:
            logger.info("Shutdown signal received, stopping...")
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    def _process_pr(self, pr: OpenPullRequest) -> None:
        """Process a single PR - dispatch review command."""
        if time.monotonic() < self._llm_retry_at:
            logger.info(
                "Skipping PR #%d in %s while LLM failure cooldown is active",
                pr.pr_id.number,
                pr.pr_id.repository,
            )
            self._record_runtime_status(DaemonState.IDLE)
            return
        force = self._force_pr == pr.pr_id.number
        failure_key = f"review:{pr.pr_id.repository}#{pr.pr_id.number}"
        try:
            self._command_failure_backoff.before_operation(failure_key)
        except RemoteOperationQuarantinedError:
            logger.warning(
                "Skipping quarantined review for PR #%d in %s",
                pr.pr_id.number,
                pr.pr_id.repository,
            )
            self._record_runtime_status(DaemonState.IDLE)
            return
        logger.info(
            "Reviewing PR #%d in %s (title=%r, sha=%s)",
            pr.pr_id.number, pr.pr_id.repository, pr.title,
            str(pr.head_sha)[:7],
        )

        active = ActiveReviewProgress(
            repository=pr.pr_id.repository,
            pr_number=pr.pr_id.number,
            pr_title=pr.title,
            head_sha=str(pr.head_sha),
            started_at=datetime.now(UTC).isoformat(),
        )
        self._record_runtime_status(DaemonState.REVIEWING, current_review=active)

        command = ReviewPullRequestCommand(
            pr_id=pr.pr_id,
            head_sha=pr.head_sha,
            title=pr.title,
            description=pr.description,
            force=force,
            review_requested=pr.review_requested,
            review_request_event_id=pr.review_request_event_id,
            latest_review_id=pr.latest_review_id,
            latest_review_dismissed=pr.latest_review_dismissed,
            target_branch=pr.target_branch,
        )

        HttpRequestCounter.instance().reset()
        failure_error: str | None = None
        try:
            result = self._review_service.execute(command)
            if not result.reviewed:
                return
            logger.info("Reviewed PR #%d in %s", pr.pr_id.number, pr.pr_id.repository)
            if self._notifier:
                if result.duration_seconds is None:
                    raise RuntimeError(
                        "Completed review did not report a duration"
                    )
                duration = self._format_duration(result.duration_seconds)
                self._notifier.notify_success(
                    (
                        "Review complete for "
                        f"{PRIdentifierService.normalize_repository(pr.pr_id.repository)} "
                        f"({duration})"
                    ),
                    f"PR #{pr.pr_id.number}",
                )
        except EmptyDiffError:
            logger.warning("Empty diff, skipping PR #%d", pr.pr_id.number)
        except RepositoryFetchError as e:
            failure_error = self._exception_message(e)
            self._cycle_error = failure_error
            logger.warning(
                "Could not fetch repository for PR #%d in %s: %s; will retry next cycle",
                pr.pr_id.number, pr.pr_id.repository, e,
            )
        except LlmUnavailableError as e:
            failure_error = self._exception_message(e)
            self._cycle_error = failure_error
            self._llm_retry_at = (
                time.monotonic() + _LLM_FAILURE_COOLDOWN_SECONDS
            )
            logger.error("LLM unavailable, will retry after cooldown")
            if self._notifier:
                self._notifier.notify_error(
                    f"LLM unavailable for PR #{pr.pr_id.number} in {pr.pr_id.repository}",
                    e,
                )
            raise
        except ReviewPublishError as e:
            failure_error = self._exception_message(e)
            self._cycle_error = failure_error
            logger.error("Publish failed for PR #%d: %s", pr.pr_id.number, e)
        except ReviewVerdictError as e:
            failure_error = self._exception_message(e)
            self._cycle_error = failure_error
            logger.warning(
                "Review inconclusive for PR #%d in %s; will retry next cycle",
                pr.pr_id.number,
                pr.pr_id.repository,
            )
        except Exception as e:
            failure_error = self._exception_message(e)
            self._cycle_error = failure_error
            logger.exception("Unexpected error processing PR #%d", pr.pr_id.number)
        finally:
            self._record_runtime_status(
                DaemonState.ERROR if failure_error is not None else DaemonState.IDLE,
                error=failure_error,
            )
            HttpRequestCounter.instance().log_summary()
            if failure_error is None:
                self._command_failure_backoff.record_success(failure_key)
            else:
                self._command_failure_backoff.record_failure(failure_key)

    @staticmethod
    def _format_duration(duration_seconds: float) -> str:
        total_seconds = max(0, int(duration_seconds))
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes}m {seconds:02d}s"

    @staticmethod
    def _exception_message(error: BaseException) -> str:
        message = str(error)
        return message or type(error).__name__

    def _qualified_pr_identity(self, pr: OpenPullRequest) -> str:
        repository = pr.pr_id.repository
        if ":" not in repository:
            platform = (
                self._config.platforms[0]
                if len(self._config.platforms) == 1
                else "forgejo"
            )
            repository = f"{platform}:{repository}"
        return f"{repository}#{pr.pr_id.number}"

    def _allowed_repos(self, repos: list[RepoInfo]) -> list[RepoInfo]:
        """Drop repositories the configured allow list does not permit."""
        if self._repository_allow_list.allows_every_repository:
            return repos

        allowed = [
            repo
            for repo in repos
            if self._repository_allow_list.allows(repo.full_name)
        ]
        self._log_repo_filtering(repos, allowed)
        return allowed

    def _log_repo_filtering(
        self, repos: list[RepoInfo], allowed: list[RepoInfo]
    ) -> None:
        """Report the number of repositories dropped by the allow list."""
        skipped_count = len(repos) - len(allowed)
        if skipped_count:
            logger.debug(
                "Skipping %d repositories not in allow list", skipped_count
            )
        if not allowed:
            logger.warning("No repositories remain after allow-list filtering")

    def _run_cycle(self) -> None:
        """Refresh settings and execute one polling cycle."""
        self._cycle_error = None
        self._check_config_reload()
        repos = self._repositories_to_poll()

        if not repos:
            logger.warning("No repositories found")
            return

        repos = self._allowed_repos(repos)

        try:
            for info in repos:
                self._process_repo(info)
        except LlmUnavailableError:
            logger.warning("LLM unavailable — cancelling this cycle")

    def _repositories_to_poll(self) -> list[RepoInfo]:
        """Build repository candidates without discovery when an allow list exists."""
        if not self._repository_allow_list.allows_every_repository:
            return [
                RepoInfo(name)
                for name in self._repository_allow_list.candidates(
                    self._config.platforms
                )
            ]
        return self._repo_lister.list_repos()

    def _process_repo(self, info: RepoInfo) -> None:
        """Process review and comment commands for one repository."""
        recent_prs = self._pr_lister.list_recent(
            info.full_name,
            (datetime.now(UTC) - timedelta(days=COMMAND_LOOKBACK_DAYS)).isoformat(),
        )
        self._process_command_prs(recent_prs)
        open_prs = self._pr_lister.list_open(info.full_name)
        self._process_command_prs(open_prs)
        open_prs = self._include_configured_force_pr(info.full_name, open_prs)
        repo_is_stale = self._repo_is_stale(info)
        actionable_prs = self._actionable_prs(open_prs, repo_is_stale)

        if not open_prs or not actionable_prs:
            self._mark_repo_seen(info)
            return

        for pr in actionable_prs:
            if pr.is_draft:
                logger.debug(f"Skipping draft PR #{pr.pr_id.number}")
                continue
            self._process_pr(pr)

        self._mark_repo_seen(info)

    def _process_command_prs(self, prs: list[OpenPullRequest]) -> None:
        service = self._process_commands_service
        repository = self._pr_repository
        if service is None or repository is None:
            return
        unique_prs = {pr.pr_id: pr for pr in prs}.values()
        for pr in unique_prs:
            self._process_command_pr(pr, service, repository)

    def _process_command_pr(
        self,
        pr: OpenPullRequest,
        service: ProcessIssueCommandsPort,
        repository: PullRequestRepositoryPort,
    ) -> None:
        stored = repository.find(pr.pr_id)
        if stored is None or not pr.updated_at:
            return
        if stored.last_command_checked_at == pr.updated_at:
            return
        failure_key = f"command:{pr.pr_id.repository}#{pr.pr_id.number}"
        try:
            self._command_failure_backoff.before_operation(failure_key)
        except RemoteOperationQuarantinedError:
            logger.warning(
                "Skipping quarantined command processing for PR #%d in %s",
                pr.pr_id.number,
                pr.pr_id.repository,
            )
            return
        try:
            service.execute(
                ProcessIssueCommandsCommand(
                    pr_id=pr.pr_id,
                    head_sha=pr.head_sha,
                )
            )
        except Exception:
            self._command_failure_backoff.record_failure(failure_key)
            logger.exception(
                "Failed to process commands for PR #%d in %s",
                pr.pr_id.number,
                pr.pr_id.repository,
            )
            return
        self._command_failure_backoff.record_success(failure_key)
        refreshed = repository.find(pr.pr_id) or stored
        repository.save(refreshed.record_command_check(pr.updated_at))

    def _include_configured_force_pr(
        self, repository: str, open_prs: list[OpenPullRequest]
    ) -> list[OpenPullRequest]:
        if self._force_pr is None:
            return open_prs
        if any(pr.pr_id.number == self._force_pr for pr in open_prs):
            return open_prs
        forced = self._pr_lister.get_pr(repository, self._force_pr)
        if forced is None:
            return open_prs
        logger.info(
            "Force-fetched PR #%d in %s (state-agnostic)",
            self._force_pr,
            repository,
        )
        return [*open_prs, forced]

    def _repo_is_stale(self, info: RepoInfo) -> bool:
        if self._update_tracker is None:
            return True
        return self._update_tracker.is_stale(info.full_name, info.pushed_at)

    def _mark_repo_seen(self, info: RepoInfo) -> None:
        if self._update_tracker is None or info.pushed_at is None:
            return
        self._update_tracker.mark_seen(info.full_name, info.pushed_at)

    def _actionable_prs(
        self, open_prs: list[OpenPullRequest], repo_is_stale: bool
    ) -> list[OpenPullRequest]:
        if repo_is_stale:
            return open_prs
        return [pr for pr in open_prs if self._is_actionable_pr(pr)]

    def _is_actionable_pr(self, pr: OpenPullRequest) -> bool:
        if pr.pr_id.number == self._force_pr:
            return True
        if self._pr_repository is None:
            actionable = pr.review_requested
        else:
            stored = self._pr_repository.find(pr.pr_id)
            if stored is None:
                return True
            actionable = stored.needs_review(pr.head_sha) or (
                pr.review_request_event_id is not None
                and pr.review_request_event_id
                > (stored.last_review_request_event_id or 0)
            ) or self._platform_review_actionable(pr, stored)
        if not actionable:
            logger.debug(
                "Skipping non-actionable PR %s: no new head, review-request "
                "event, dismissed platform review, or force trigger was present",
                self._qualified_pr_identity(pr),
            )
        return actionable

    @staticmethod
    def _platform_review_actionable(
        pr: OpenPullRequest, stored: PullRequest
    ) -> bool:
        if not pr.latest_review_dismissed or pr.latest_review_id is None:
            return False
        if stored.last_platform_review_id is None:
            return True
        if pr.latest_review_id > stored.last_platform_review_id:
            return True
        return (
            pr.latest_review_id == stored.last_platform_review_id
            and not stored.last_platform_review_dismissed
        )
