"""PollingDaemon - polls repositories for open PRs and triggers reviews."""

from __future__ import annotations

import logging
import signal
import time
from datetime import UTC, datetime, timedelta

from pr_auto_reviewer.application.services.pr_identifier_service import (
    PRIdentifierService,
)
from pr_auto_reviewer.application.ports.inbound.process_issue_commands_port import (
    ProcessIssueCommandsPort,
)
from pr_auto_reviewer.application.ports.inbound.review_pull_request_port import (
    ReviewPullRequestPort,
)
from pr_auto_reviewer.application.ports.outbound.notifier_port import NotifierPort
from pr_auto_reviewer.application.ports.outbound.pull_request_repository_port import (
    PullRequestRepositoryPort,
)
from pr_auto_reviewer.domain.exceptions.empty_diff_error import EmptyDiffError
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.exceptions.repository_fetch_error import (
    RepositoryFetchError,
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
from pr_auto_reviewer.infrastructure.client.http_request_counter import (
    HttpRequestCounter,
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

logger = logging.getLogger(__name__)
COMMAND_LOOKBACK_DAYS = 7


class PollingDaemon:

    def __init__(
        self,
        config: PollingDaemonConfig,
        repo_lister: RepoListerPort,
        pr_lister: PrListerPort,
        review_service: ReviewPullRequestPort,
        notifier: NotifierPort | None = None,
        update_tracker: RepoUpdateTracker | None = None,
        repository_allow_list: RepositoryAllowList | None = None,
        process_commands_service: ProcessIssueCommandsPort | None = None,
        pr_repository: PullRequestRepositoryPort | None = None,
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
        self._force_pr = getattr(config, "force_pr", None)
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
        try:
            while True:
                cycle += 1
                self._run_cycle()

                if self._config.run_once:
                    break

                time.sleep(self._config.poll_interval_seconds)
        except KeyboardInterrupt:
            pass

        logger.info(f"PollingDaemon stopped after {cycle} cycle(s)")

    def _setup_signal_handlers(self) -> None:
        def handle_signal(signum: int, frame: object) -> None:
            logger.info("Shutdown signal received, stopping...")
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    def _process_pr(self, pr: OpenPullRequest) -> None:
        """Process a single PR - dispatch review command."""
        force = self._force_pr == pr.pr_id.number
        logger.info(
            "Reviewing PR #%d in %s (title=%r, sha=%s)",
            pr.pr_id.number, pr.pr_id.repository, pr.title,
            str(pr.head_sha)[:7],
        )

        command = ReviewPullRequestCommand(
            pr_id=pr.pr_id,
            head_sha=pr.head_sha,
            title=pr.title,
            description=pr.description,
            force=force,
            review_requested=pr.review_requested,
            review_request_event_id=pr.review_request_event_id,
            target_branch=pr.target_branch,
        )

        HttpRequestCounter.instance().reset()
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
            logger.warning(
                "Could not fetch repository for PR #%d in %s: %s; will retry next cycle",
                pr.pr_id.number, pr.pr_id.repository, e,
            )
        except LlmUnavailableError as e:
            logger.error("LLM unavailable, will retry next cycle")
            if self._notifier:
                self._notifier.notify_error(
                    f"LLM unavailable for PR #{pr.pr_id.number} in {pr.pr_id.repository}",
                    e,
                )
            raise
        except ReviewPublishError as e:
            logger.error("Publish failed for PR #%d: %s", pr.pr_id.number, e)
        except ReviewVerdictError:
            logger.warning(
                "Review inconclusive for PR #%d in %s; will retry next cycle",
                pr.pr_id.number,
                pr.pr_id.repository,
            )
        except Exception as _:
            logger.exception("Unexpected error processing PR #%d", pr.pr_id.number)
        finally:
            HttpRequestCounter.instance().log_summary()

    @staticmethod
    def _format_duration(duration_seconds: float) -> str:
        total_seconds = max(0, int(duration_seconds))
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes}m {seconds:02d}s"

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
        """Execute one polling cycle."""
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
        self._mark_repo_seen(info)
        actionable_prs = self._actionable_prs(open_prs, repo_is_stale)

        if not open_prs or not actionable_prs:
            return

        for pr in actionable_prs:
            if pr.is_draft:
                logger.debug(f"Skipping draft PR #{pr.pr_id.number}")
                continue
            self._process_pr(pr)

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
        try:
            service.execute(
                ProcessIssueCommandsCommand(
                    pr_id=pr.pr_id,
                    head_sha=pr.head_sha,
                )
            )
        except Exception:
            logger.exception(
                "Failed to process commands for PR #%d in %s",
                pr.pr_id.number,
                pr.pr_id.repository,
            )
            return
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
        return [
            pr
            for pr in open_prs
            if pr.review_requested or pr.pr_id.number == self._force_pr
        ]
