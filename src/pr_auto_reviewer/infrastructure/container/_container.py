"""Container — DI container that owns all infrastructure-layer objects."""

from __future__ import annotations

from pathlib import Path

import logging


from pr_auto_reviewer.infrastructure.config import Config, load_config
from pr_auto_reviewer.infrastructure.container._platform_clients import wire_platform_clients
from pr_auto_reviewer.infrastructure.container._platform_adapters import wire_platform_adapters
from pr_auto_reviewer.infrastructure.container._core_services import wire_core_services
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.persistence.null_pr_repository import (
    NullPullRequestRepository,
)


from pr_auto_reviewer.application.ports.outbound.changeset_fetcher_port import (
    ChangesetFetcherPort,
)
from pr_auto_reviewer.application.ports.outbound.comment_publisher_port import (
    CommentPublisherPort,
)
from pr_auto_reviewer.application.ports.outbound.comment_reader_port import (
    CommentReaderPort,
)
from pr_auto_reviewer.application.ports.outbound.issue_tracker_port import (
    IssueTrackerPort,
)
from pr_auto_reviewer.application.ports.outbound.notifier_port import (
    NotifierPort,
)
from pr_auto_reviewer.application.ports.outbound.token_verifier_port import (
    TokenVerifierPort,
)

from pr_auto_reviewer.application.ports.outbound.fragment_repository_port import (
    FragmentRepositoryPort,
)
from pr_auto_reviewer.application.ports.outbound.llm_review_port import (
    LlmReviewPort,
)
from pr_auto_reviewer.application.ports.outbound.prompt_renderer_port import (
    PromptRendererPort,
)
from pr_auto_reviewer.application.ports.outbound.pull_request_repository import (
    PullRequestRepository,
)
from pr_auto_reviewer.application.ports.outbound.repository_context_port import (
    RepositoryContextPort,
)
from pr_auto_reviewer.application.ports.outbound.review_context_factory_port import (
    ReviewContextFactoryPort,
)
from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.application.ports.outbound.review_reader_port import (
    ReviewReaderPort,
)
from pr_auto_reviewer.application.ports.outbound.command_bus_port import (
    CommandBusPort,
)
from pr_auto_reviewer.presentation.ports import PrListerPort, RepoListerPort
logger = logging.getLogger(__name__)


class Container:
    """Dependency-injection container.  Creates and wires all infrastructure
    adapters based on Config."""

    def _wire(self) -> None:
        is_terminal = self._config.output_mode == "terminal"
        clients = wire_platform_clients(self._config)
        self._http_client = clients.http_client
        self._reviewer_client = clients.reviewer_client
        self._token_verifier = clients.token_verifier

        from pr_auto_reviewer.infrastructure.local_repository.local_git_repository import (
            LocalGitRepository,
        )
        local_repository = LocalGitRepository(Path(self._config.local_clone_base_dir))
        adapters = wire_platform_adapters(
            self._config, clients, is_terminal, local_repository=local_repository
        )
        self._repository_context = adapters.repository_context
        self._changeset_fetcher = adapters.changeset_fetcher
        self._review_publisher = adapters.review_publisher
        self._review_reader = adapters.review_reader
        self._comment_reader = adapters.comment_reader
        self._comment_publisher = adapters.comment_publisher
        self._issue_tracker = adapters.issue_tracker
        self._repo_lister = adapters.repo_lister
        self._pr_lister = adapters.pr_lister

        core = wire_core_services(
            self._config, self._repository_context
        )
        self._pr_repository = core.pr_repository
        self._llm_review = core.llm_review
        self._command_bus = core.command_bus
        self._conversation_logger = core.conversation_logger
        self._notifier = core.notifier
        self._fragment_repository = core.fragment_repository
        self._fragment_renderer = core.fragment_renderer
        self._fragment_max_tokens = core.fragment_max_tokens
        self._review_context_factory = core.review_context_factory

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or load_config()
        self._pr_repository: PullRequestRepository = NullPullRequestRepository()
        self._wire()

    @property
    def config(self) -> Config:
        return self._config

    @property
    def http_client(self) -> GitPlatformHttpClient:
        return self._http_client

    @property
    def reviewer_client(self) -> GitPlatformHttpClient:
        return self._reviewer_client

    @property
    def pr_repository(self) -> PullRequestRepository:
        return self._pr_repository

    @property
    def changeset_fetcher(self) -> ChangesetFetcherPort:
        return self._changeset_fetcher

    @property
    def repository_context(self) -> RepositoryContextPort:
        return self._repository_context

    @property
    def llm_review(self) -> LlmReviewPort:
        return self._llm_review

    @property
    def review_publisher(self) -> ReviewPublisherPort:
        return self._review_publisher

    @property
    def conversation_logger(self) -> MarkdownConversationLogger:
        return self._conversation_logger

    @property
    def review_reader(self) -> ReviewReaderPort:
        return self._review_reader

    @property
    def comment_reader(self) -> CommentReaderPort:
        return self._comment_reader

    @property
    def comment_publisher(self) -> CommentPublisherPort:
        return self._comment_publisher

    @property
    def issue_tracker(self) -> IssueTrackerPort:
        return self._issue_tracker

    @property
    def command_bus(self) -> CommandBusPort:
        return self._command_bus

    @property
    def repo_lister(self) -> RepoListerPort:
        return self._repo_lister

    @property
    def pr_lister(self) -> PrListerPort:
        return self._pr_lister

    @property
    def review_context_factory(self) -> ReviewContextFactoryPort:
        return self._review_context_factory

    @property
    def fragment_repository(self) -> FragmentRepositoryPort:
        return self._fragment_repository

    @property
    def notifier(self) -> NotifierPort:
        return self._notifier

    @property
    def token_verifier(self) -> TokenVerifierPort:
        return self._token_verifier

    @property
    def fragment_renderer(self) -> PromptRendererPort:
        return self._fragment_renderer

    @property
    def fragment_max_tokens(self) -> int | None:
        return self._fragment_max_tokens
