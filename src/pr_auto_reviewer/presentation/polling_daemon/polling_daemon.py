"""PollingDaemon - polls repositories for open PRs and triggers reviews."""

from __future__ import annotations

import logging
import signal
import time

from pr_auto_reviewer.application.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.application.ports.inbound.review_pull_request_use_case import (
    ReviewPullRequestUseCase,
)
from pr_auto_reviewer.domain.exceptions.empty_diff_error import EmptyDiffError
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.exceptions.review_publish_error import ReviewPublishError
from pr_auto_reviewer.presentation.ports import OpenPullRequest, PrListerPort, RepoListerPort
from pr_auto_reviewer.presentation.polling_daemon.polling_daemon_config import (
    PollingDaemonConfig,
)

logger = logging.getLogger(__name__)


class PollingDaemon:
    """Polls repositories for open PRs and triggers review operations."""

    def __init__(
        self,
        config: PollingDaemonConfig,
        repo_lister: RepoListerPort,
        pr_lister: PrListerPort,
        review_service: ReviewPullRequestUseCase,
    ) -> None:
        self._config = config
        self._repo_lister = repo_lister
        self._pr_lister = pr_lister
        self._review_service = review_service
        self._force_pr = getattr(config, "force_pr", None)
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        def handle_signal(signum: int, frame: object) -> None:
            logger.info("Shutdown signal received, stopping...")
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    def start(self) -> None:
        """Start the polling loop."""
        logger.info(
            f"Starting PollingDaemon (interval={self._config.poll_interval_seconds}s, "
            f"run_once={self._config.run_once})"
        )

        try:
            while True:
                self._run_cycle()

                if self._config.run_once:
                    break

                time.sleep(self._config.poll_interval_seconds)
        except KeyboardInterrupt:
            pass

        logger.info("PollingDaemon stopped")

    def _run_cycle(self) -> None:
        """Execute one polling cycle."""
        repos = self._repo_lister.list_repos()

        if not repos:
            logger.warning("No repositories found")
            return

        for repo in repos:
            open_prs = self._pr_lister.list_open(repo)

            # If force_pr is set, also fetch that specific PR (may be closed/merged)
            if self._force_pr is not None:
                forced = self._pr_lister.get_pr(repo, self._force_pr)
                if forced is not None:
                    # Avoid duplicates: only add if not already in open_prs
                    if not any(p.pr_id.number == self._force_pr for p in open_prs):
                        open_prs.append(forced)
                        logger.info(
                            "Force-fetched PR #%d in %s (state-agnostic)",
                            self._force_pr, repo,
                        )

            if not open_prs:
                logger.debug(f"No open PRs in {repo}")
                continue

            for pr in open_prs:
                if pr.is_draft:
                    logger.debug(f"Skipping draft PR #{pr.pr_id.number}")
                    continue

                self._process_pr(pr)

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
        )

        try:
            self._review_service.execute(command)
            logger.info("Reviewed PR #%d in %s", pr.pr_id.number, pr.pr_id.repository)
        except EmptyDiffError:
            logger.warning("Empty diff, skipping PR #%d", pr.pr_id.number)
        except LlmUnavailableError:
            logger.error("LLM unavailable, will retry next cycle")
        except ReviewPublishError as e:
            logger.error("Publish failed for PR #%d: %s", pr.pr_id.number, e)
        except Exception as e:
            logger.exception("Unexpected error processing PR #%d: %s", pr.pr_id.number, e)
