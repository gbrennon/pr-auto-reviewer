"""Container — DI container that owns all infrastructure-layer objects."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

from pr_auto_reviewer.infrastructure.config import Config, load_config
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.forgejo.changeset_fetcher import (
    ForgejoChangesetFetcher,
)
from pr_auto_reviewer.infrastructure.github.changeset_fetcher import (
    GithubChangesetFetcher,
)
from pr_auto_reviewer.infrastructure.forgejo.comment_publisher import (
    ForgejoCommentPublisher,
)
from pr_auto_reviewer.infrastructure.forgejo.comment_reader import (
    ForgejoCommentReader,
)
from pr_auto_reviewer.infrastructure.forgejo.issue_tracker import (
    ForgejoIssueTracker,
)
from pr_auto_reviewer.infrastructure.forgejo.pr_lister import (
    ForgejoPrLister,
)
from pr_auto_reviewer.infrastructure.forgejo.repo_lister import (
    ForgejoRepoLister,
)
from pr_auto_reviewer.infrastructure.forgejo.repository_context import (
    ForgejoRepositoryContext,
)
from pr_auto_reviewer.infrastructure.forgejo.review_reader import (
    ForgejoReviewReader,
)


from pr_auto_reviewer.infrastructure.review_publishers.platform_publisher import (
    PlatformReviewPublisherAdapter,
)
from pr_auto_reviewer.infrastructure.review_publishers.terminal_publisher import (
    TerminalReviewPublisherAdapter,
)
from pr_auto_reviewer.infrastructure.llm.ollama_llm_adapter import OllamaLlmAdapter
from pr_auto_reviewer.infrastructure.persistence.json_file_pr_repository import (
    JsonFilePullRequestRepository,
)
from pr_auto_reviewer.infrastructure.persistence.null_pr_repository import (
    NullPullRequestRepository,
)
from pr_auto_reviewer.infrastructure.fragments.compose_review_prompt_adapter import (
    ComposeReviewPromptAdapter,
)
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)
from pr_auto_reviewer.infrastructure.fragments.repositories import (
    FileSystemFragmentRepository,
)
from pr_auto_reviewer.infrastructure.context.review_context_factory import (
    ReviewContextFactory,
)
from pr_auto_reviewer.infrastructure.fragments.renderers import (
    Jinja2Renderer,
)
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider
from pr_auto_reviewer.infrastructure.review_publishers.composite_publisher import (
    CompositeReviewPublisher,
)
from pr_auto_reviewer.infrastructure.git_platform.multi_platform import (
    CompositeRepoLister,
    CompositePrLister,
    CompositeChangesetFetcher,
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
from pr_auto_reviewer.application.ports.outbound.compose_review_prompt_port import (
    ComposeReviewPromptPort,
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


class Container:
    """Dependency-injection container.  Creates and wires all infrastructure
    adapters based on Config."""

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or load_config()
        self._pr_repository: PullRequestRepository = NullPullRequestRepository()
        self._wire()

    def _wire(self) -> None:
        is_terminal = self._config.output_mode == "terminal"

        if self._config.platform_mode == GitProvider.BOTH:
            gb_owner = GitPlatformHttpClient(
                self._config.github_api_url,
                self._config.github_owner_token,
                "github",
                "owner",
            )
            gb_reviewer = GitPlatformHttpClient(
                self._config.github_api_url,
                self._config.github_reviewer_token,
                "github",
                "reviewer",
            )
            fj_owner = GitPlatformHttpClient(
                self._config.forgejo_api_url,
                self._config.forgejo_owner_token,
                "forgejo",
                "owner",
            )
            fj_reviewer = GitPlatformHttpClient(
                self._config.forgejo_api_url,
                self._config.forgejo_reviewer_token,
                "forgejo",
                "reviewer",
            )

            self._repository_context: RepositoryContextPort = ForgejoRepositoryContext(
                fj_owner
            )
            self._changeset_fetcher: ChangesetFetcherPort = CompositeChangesetFetcher(
                GithubChangesetFetcher(gb_owner),
                ForgejoChangesetFetcher(fj_owner),
                default_platform="codeberg",
            )

            self._review_publisher: ReviewPublisherPort = (
                TerminalReviewPublisherAdapter(self._config.output_path)
                if is_terminal
                else CompositeReviewPublisher(
                    {
                        "github": PlatformReviewPublisherAdapter(
                            gb_reviewer,
                            self._config.github_reviewer_token or "",
                            self._config.github_reviewer_username,
                            owner_client=gb_owner,
                            review_mode=self._config.github_review_mode,
                        ),
                        "forgejo": PlatformReviewPublisherAdapter(
                            fj_reviewer,
                            self._config.forgejo_reviewer_token or "",
                            self._config.forgejo_reviewer_username,
                            owner_client=fj_owner,
                        ),
                    }
                )
            )
            self._review_reader = ForgejoReviewReader(gb_owner)
            self._comment_reader = ForgejoCommentReader(gb_owner)
            self._comment_publisher = ForgejoCommentPublisher(gb_reviewer)
            self._issue_tracker = ForgejoIssueTracker(gb_owner)

            self._repo_lister: RepoListerPort = CompositeRepoLister(
                {
                    "github": ForgejoRepoLister(gb_owner),
                    "forgejo": ForgejoRepoLister(fj_owner),
                }
            )
            self._pr_lister: PrListerPort = CompositePrLister(
                {
                    "github": ForgejoPrLister(gb_owner),
                    "forgejo": ForgejoPrLister(fj_owner),
                }
            )
        else:
            is_github = self._config.platform_mode == GitProvider.GITHUB
            api_url = (
                self._config.github_api_url
                if is_github
                else self._config.forgejo_api_url
            )
            owner_token = (
                self._config.github_owner_token
                if is_github
                else self._config.forgejo_owner_token
            )
            reviewer_token = (
                (self._config.github_reviewer_token or self._config.github_owner_token)
                if is_github
                else (
                    self._config.forgejo_reviewer_token
                    or self._config.forgejo_owner_token
                )
            )
            reviewer_username = (
                self._config.github_reviewer_username
                if is_github
                else self._config.forgejo_reviewer_username
            )
            platform_value = self._config.platform_mode.value

            self._http_client = GitPlatformHttpClient(
                api_url,
                owner_token,
                platform_value,
                "owner",
            )
            self._reviewer_client = GitPlatformHttpClient(
                api_url,
                reviewer_token,
                platform_value,
                "reviewer",
            )

            self._repository_context: RepositoryContextPort = ForgejoRepositoryContext(
                self._http_client
            )
            self._changeset_fetcher: ChangesetFetcherPort = (
                GithubChangesetFetcher(self._http_client)
                if is_github
                else ForgejoChangesetFetcher(self._http_client)
            )

            self._review_publisher: ReviewPublisherPort = (
                TerminalReviewPublisherAdapter(self._config.output_path)
                if is_terminal
                else PlatformReviewPublisherAdapter(
                    self._reviewer_client,
                    reviewer_token,
                    reviewer_username,
                    owner_client=self._http_client,
                )
            )
            self._review_reader: ReviewReaderPort = ForgejoReviewReader(
                self._http_client
            )
            self._comment_reader: CommentReaderPort = ForgejoCommentReader(
                self._http_client
            )
            self._comment_publisher: CommentPublisherPort = ForgejoCommentPublisher(
                self._reviewer_client
            )
            self._issue_tracker: IssueTrackerPort = ForgejoIssueTracker(
                self._http_client
            )
            self._pr_lister: PrListerPort = ForgejoPrLister(self._http_client)
            self._repo_lister: RepoListerPort = ForgejoRepoLister(self._http_client)

        self._pr_repository = JsonFilePullRequestRepository(_state_file_path())
        self._llm_review: LlmReviewPort = OllamaLlmAdapter(
            self._config.llm_host,
            self._config.llm_model or "code-review:latest",
        )
        self._command_bus: CommandBusPort = InMemoryCommandBus()

        fragments_dir = self._config.fragments_dir or None
        self._fragment_repository: FragmentRepositoryPort = (
            FileSystemFragmentRepository(Path(fragments_dir))
            if fragments_dir
            else FileSystemFragmentRepository()
        )
        self._fragment_renderer: PromptRendererPort = Jinja2Renderer()
        self._fragment_max_tokens: int | None = getattr(
            self._config, "fragment_max_tokens", None
        )

        prompt_adapter: ComposeReviewPromptPort = ComposeReviewPromptAdapter(
            repository=self._fragment_repository,
            renderer=self._fragment_renderer,
            max_tokens=self._fragment_max_tokens,
            max_total_chars=self._config.max_prompt_tokens * 4
            if self._config.max_prompt_tokens > 0
            else 60_000,
            use_strict_selection=getattr(
                self._config, "use_strict_fragment_selection", False
            ),
        )
        self._review_context_factory: ReviewContextFactoryPort = ReviewContextFactory(
            repository_context=self._repository_context,
            compose_review_prompt=prompt_adapter,
        )

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
    def fragment_renderer(self) -> PromptRendererPort:
        return self._fragment_renderer

    @property
    def fragment_max_tokens(self) -> int | None:
        return self._fragment_max_tokens


def _state_file_path() -> str:
    config_dir = os.path.expanduser("~/.config/pr-auto-reviewer")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "state.json")
