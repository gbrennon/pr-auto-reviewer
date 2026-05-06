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
        self._shutdown_requested = False
        self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        def handle_signal(signum: int, frame: object) -> None:
            logger.info("Shutdown signal received, finishing current cycle...")
            self._shutdown_requested = True

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    def start(self) -> None:
        """Start the polling loop."""
        logger.info(
            f"Starting PollingDaemon (interval={self._config.poll_interval_seconds}s, "
            f"run_once={self._config.run_once})"
        )

        while not self._shutdown_requested:
            self._run_cycle()

            if self._config.run_once or self._shutdown_requested:
                break

            time.sleep(self._config.poll_interval_seconds)

        logger.info("PollingDaemon stopped")

    def _run_cycle(self) -> None:
        """Execute one polling cycle."""
        repos = self._repo_lister.list_repos()

        if not repos:
            logger.warning("No repositories found")
            return

        for repo in repos:
            if self._shutdown_requested:
                break

            open_prs = self._pr_lister.list_open(repo)

            if not open_prs:
                logger.debug(f"No open PRs in {repo}")
                continue

            for pr in open_prs:
                if self._shutdown_requested:
                    break

                if pr.is_draft:
                    logger.debug(f"Skipping draft PR #{pr.pr_id.number}")
                    continue

                self._process_pr(pr)

    def _process_pr(self, pr: OpenPullRequest) -> None:
        """Process a single PR - dispatch review command."""
        logger.info(f"Reviewing PR #{pr.pr_id.number} in {pr.pr_id.repository}")

        command = ReviewPullRequestCommand(
            pr_id=pr.pr_id,
            head_sha=pr.head_sha,
            title=pr.title,
        )

        try:
            self._review_service.execute(command)
        except EmptyDiffError:
            logger.warning(f"Empty diff, skipping PR #{pr.pr_id.number}")
        except LlmUnavailableError:
            logger.error("LLM unavailable, will retry next cycle")
        except ReviewPublishError as e:
            logger.error(f"Publish failed for PR #{pr.pr_id.number}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error processing PR #{pr.pr_id.number}: {e}")