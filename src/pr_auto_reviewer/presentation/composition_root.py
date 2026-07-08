"""CompositionRoot — wires all layers and exposes application entry points."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from pr_auto_reviewer.application.ports.inbound.process_issue_commands_use_case import (
    ProcessIssueCommandsUseCase,
)
from pr_auto_reviewer.application.ports.inbound.review_pull_request_use_case import (
    ReviewPullRequestUseCase,
)
from pr_auto_reviewer.application.ports.outbound.notifier import Notifier
from pr_auto_reviewer.application.ports.outbound.review_reader_port import (
    ReviewReaderPort,
)
from pr_auto_reviewer.application.services.process_issue_commands_service import (
    ProcessIssueCommandsService,
)
from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.application.serializers.issue_body_builder import (
    IssueBodyBuilder,
)
from pr_auto_reviewer.domain.services.issue_command_parser import IssueCommandParser
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser
from pr_auto_reviewer.infrastructure.config import load_config
from pr_auto_reviewer.infrastructure.container import Container
from pr_auto_reviewer.presentation.cli.runner import CliRunner
from pr_auto_reviewer.presentation.polling_daemon import (
    PollingDaemon,
    PollingDaemonConfig,
)
from pr_auto_reviewer.presentation.ports import PrListerPort, RepoListerPort

logger = logging.getLogger(__name__)

@dataclass
class ApplicationComponents:
    """All application components wired together."""

    review_service: ReviewPullRequestUseCase
    process_commands_service: ProcessIssueCommandsUseCase
    review_reader: ReviewReaderPort
    pr_lister: PrListerPort
    repo_lister: RepoListerPort
    review_item_parser: ReviewItemParser
    cli_runner: CliRunner
    notifier: Notifier | None = None

class CompositionRoot:
    """Wires infrastructure, application and presentation layers.

    Creates the DI container, builds application services, and exposes
    fully-wired presentation-layer entry points.
    """

    def __init__(self, config_path: str | None = None) -> None:
        _ = config_path
        config = load_config()
        self._setup_logging(config.debug)
        self._container = Container(config)
        self._components = self._wire_components()

    @staticmethod
    def _setup_logging(debug: bool) -> None:
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            force=True,
        )
        logging.getLogger("pr_auto_reviewer").setLevel(log_level)
        if not debug:
            logging.getLogger("urllib3").setLevel(logging.WARNING)
            logging.getLogger("requests").setLevel(logging.WARNING)

    def _wire_components(self) -> ApplicationComponents:
        c = self._container

        review_service = ReviewPullRequestService(
            pr_repository=c.pr_repository,
            changeset_fetcher=c.changeset_fetcher,
            review_context_factory=c.review_context_factory,
            llm_review=c.llm_review,
            review_publisher=c.review_publisher,
        )

        review_item_parser = ReviewItemParser()
        issue_command_parser = IssueCommandParser()
        issue_body_builder = IssueBodyBuilder()

        process_commands_service = ProcessIssueCommandsService(
            pr_repository=c.pr_repository,
            review_reader=c.review_reader,
            comment_reader=c.comment_reader,
            comment_publisher=c.comment_publisher,
            issue_tracker=c.issue_tracker,
            review_item_parser=review_item_parser,
            issue_command_parser=issue_command_parser,
            issue_body_builder=issue_body_builder,
        )

        cli_runner = CliRunner(
            review_service=review_service,
            process_commands_service=process_commands_service,
            review_reader=c.review_reader,
            pr_lister=c.pr_lister,
            review_item_parser=review_item_parser,
            pr_repository=c.pr_repository,
        )

        return ApplicationComponents(
            review_service=review_service,
            process_commands_service=process_commands_service,
            review_reader=c.review_reader,
            pr_lister=c.pr_lister,
            repo_lister=c.repo_lister,
            review_item_parser=review_item_parser,
            cli_runner=cli_runner,
        )

    @property
    def components(self) -> ApplicationComponents:
        return self._components

    @property
    def container(self) -> Container:
        return self._container

    def run_daemon(self) -> None:
        config = load_config()
        poll_interval = int(
            os.environ.get("POLL_INTERVAL", config.poll_interval),
        )
        run_once = os.environ.get("RUN_ONCE", "false").lower() == "true"
        repos_filter = os.environ.get("REPOS_FILTER")
        force_pr_str = os.environ.get("FORCE_PR")
        force_pr = int(force_pr_str) if force_pr_str else None

        daemon_config = PollingDaemonConfig(
            poll_interval_seconds=poll_interval,
            repos_filter=repos_filter,
            run_once=run_once,
            force_pr=force_pr,
        )

        daemon = PollingDaemon(
            config=daemon_config,
            repo_lister=self._components.repo_lister,
            pr_lister=self._components.pr_lister,
            review_service=self._components.review_service,
            notifier=self._components.notifier,
        )

        daemon.start()

def bootstrap() -> ApplicationComponents:
    """Backward-compatible entry point.  Delegates to CompositionRoot."""
    root = CompositionRoot()
    return root.components

def run_daemon(components: ApplicationComponents | None = None) -> None:
    """Backward-compatible daemon runner."""
    if components is None:
        root = CompositionRoot()
        root.run_daemon()
    else:
        root = CompositionRoot()
        root._components = components
        root.run_daemon()
