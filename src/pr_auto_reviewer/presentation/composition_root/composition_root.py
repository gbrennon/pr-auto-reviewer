from ._shared import *
from .application_components import ApplicationComponents


class CompositionRoot:
    """Wires infrastructure, application and presentation layers.

    Creates the DI container, builds application services, and exposes
    fully-wired presentation-layer entry points.
    """

    def __init__(
        self,
        config_path: str | None = None,
        *,
        notifier: NotifierPort | None = None,
    ) -> None:
        _ = config_path
        config = load_config()
        self._setup_logging(config.debug)
        self._notifier_override = notifier
        self._container = Container(config)
        self._components = self._wire_components()

    @property
    def components(self) -> ApplicationComponents:
        return self._components

    @property
    def container(self) -> Container:
        return self._container

    def _setup_logging(self, debug: bool) -> None:
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

    def run_daemon(self) -> None:
        config = self._container.config if hasattr(self, '_container') else load_config()

        daemon_config = PollingDaemonConfig(
            poll_interval_seconds=config.poll_interval,
            repos_filter=config.repos_filter or None,
            run_once=config.run_once,
            force_pr=config.force_pr,
        )

        daemon = PollingDaemon(
            config=daemon_config,
            repo_lister=self._components.repo_lister,
            pr_lister=self._components.pr_lister,
            review_service=self._components.review_service,
            notifier=self._components.notifier,
            update_tracker=RepoUpdateTracker(),
        )

        daemon.start()

    def _wire_components(self) -> ApplicationComponents:
        c = self._container
        notifier = (
            self._notifier_override
            if self._notifier_override is not None
            else c.notifier
        )

        review_service = ReviewPullRequestService(
            pr_repository=c.pr_repository,
            changeset_fetcher=c.changeset_fetcher,
            review_context_factory=c.review_context_factory,
            llm_review=c.llm_review,
            review_publisher=c.review_publisher,
            token_verifier=c.token_verifier,
            command_bus=c.command_bus,
            conversation_logger=c.conversation_logger,
            plan=c.review_plan,
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
            notifier=notifier,
            token_verifier=c.token_verifier,
            output_mode=c.config.output_mode,
        )

        return ApplicationComponents(
            review_service=review_service,
            process_commands_service=process_commands_service,
            review_reader=c.review_reader,
            pr_lister=c.pr_lister,
            repo_lister=c.repo_lister,
            review_item_parser=review_item_parser,
            cli_runner=cli_runner,
            notifier=notifier,
            token_verifier=c.token_verifier,
        )

