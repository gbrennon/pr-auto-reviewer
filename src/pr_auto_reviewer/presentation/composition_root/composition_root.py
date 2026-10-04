import logging

from pr_auto_reviewer.application.ports.outbound.git_credential_provider_port import (
    GitCredentialProviderPort,
)
from pr_auto_reviewer.application.services.issue_content_preparer_service import (
    IssueContentPreparerService,
)
from pr_auto_reviewer.application.services.list_allowed_repositories_service import (
    ListAllowedRepositoriesService,
)
from pr_auto_reviewer.application.services.register_issue_service import (
    RegisterIssueService,
)
from pr_auto_reviewer.domain.messages.commands.register_issue_command import (
    RegisterIssueCommand,
)
from pr_auto_reviewer.domain.services.repository_allow_list import (
    RepositoryAllowList,
)
from pr_auto_reviewer.infrastructure.git_credentials import (
    InteractiveGitCredentialPrompter,
)
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider
from pr_auto_reviewer.infrastructure.config.repository_allow_list_entries import (
    ConfiguredRepositoryAllowListEntries,
)

from ._shared import *
from .application_components import ApplicationComponents

logger = logging.getLogger(__name__)


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
        credential_provider: GitCredentialProviderPort | None = None,
    ) -> None:
        _ = config_path
        config = load_config()
        self._setup_logging(config.debug)
        self._notifier_override = notifier
        self._credential_provider = credential_provider
        self._container = Container(config)
        self._components = self._wire_components()

    @property
    def components(self) -> ApplicationComponents:
        return self._components

    @property
    def container(self) -> Container:
        return self._container

    def run_daemon(self) -> None:
        config = self._container.config if hasattr(self, '_container') else load_config()

        daemon_config = PollingDaemonConfig(
            poll_interval_seconds=config.poll_interval,
            repos_filter=config.repos_filter or None,
            repos_allow_list=config.repos_allow_list,
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
            repository_allow_list=RepositoryAllowList.from_entries(
                config.repos_allow_list
            ),
            process_commands_service=self._components.process_commands_service,
            pr_repository=self._container.pr_repository,
        )

        self._authenticate_for_git_host(config)
        daemon.start()

    def _setup_logging(self, debug: bool) -> None:
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            force=True,
        )
        logging.getLogger("pr_auto_reviewer").setLevel(log_level)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)

    def _git_host(self, config) -> str:
        if config.platform_mode == GitProvider.GITHUB:
            return "github.com"
        return "codeberg.org"

    def _authenticate_for_git_host(self, config) -> None:
        provider = self._credential_provider
        if provider is None:
            provider = InteractiveGitCredentialPrompter()
        protocol = config.clone_protocol.value
        host = self._git_host(config)
        credentials = provider.prompt(protocol, host)
        if credentials is None:
            logger.warning(
                "No git credentials provided for %s over %s; "
                "clones may fail with authentication errors.",
                host, protocol,
            )
            return
        self._container.local_repository.credentials = credentials

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
        list_allowed_repositories = ListAllowedRepositoriesService(
            ConfiguredRepositoryAllowListEntries(c.config.repos_allow_list)
        )

        issue_content_preparer = IssueContentPreparerService(
            chat_port=c.chat_client,
            issue_body_builder=issue_body_builder,
        )
        register_issue_service = RegisterIssueService(
            pr_repository=c.pr_repository,
            issue_content_preparer=issue_content_preparer,
            issue_tracker=c.issue_tracker,
        )
        c.command_bus.register(
            RegisterIssueCommand, register_issue_service.execute
        )

        process_commands_service = ProcessIssueCommandsService(
            pr_repository=c.pr_repository,
            comment_reader=c.comment_reader,
            comment_publisher=c.comment_publisher,
            issue_command_parser=issue_command_parser,
            command_bus=c.command_bus,
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
            list_allowed_repositories=list_allowed_repositories,
        )

        return ApplicationComponents(
            review_service=review_service,
            process_commands_service=process_commands_service,
            review_reader=c.review_reader,
            pr_lister=c.pr_lister,
            repo_lister=c.repo_lister,
            review_item_parser=review_item_parser,
            cli_runner=cli_runner,
            list_allowed_repositories=list_allowed_repositories,
            notifier=notifier,
            token_verifier=c.token_verifier,
        )

