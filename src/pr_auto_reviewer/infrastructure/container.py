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
from pr_auto_reviewer.infrastructure.git_platform.changeset_fetcher import (
    GitChangesetFetcherAdapter,
)
from pr_auto_reviewer.infrastructure.git_platform.comment_publisher import (
    GitCommentPublisherAdapter,
)
from pr_auto_reviewer.infrastructure.git_platform.comment_reader import (
    GitCommentReaderAdapter,
)
from pr_auto_reviewer.infrastructure.git_platform.issue_tracker import (
    GitIssueTrackerAdapter,
)
from pr_auto_reviewer.infrastructure.git_platform.pr_lister_adapter import (
    GitPrListerAdapter,
)
from pr_auto_reviewer.infrastructure.git_platform.repo_lister_adapter import (
    GitRepoListerAdapter,
)
from pr_auto_reviewer.infrastructure.git_platform.repository_context import (
    GitRepositoryContextAdapter,
)
from pr_auto_reviewer.infrastructure.git_platform.review_publisher import (
    GitReviewPublisherAdapter,
)
from pr_auto_reviewer.infrastructure.git_platform.terminal_review_publisher import (
    TerminalReviewPublisherAdapter,
)
from pr_auto_reviewer.infrastructure.git_platform.review_reader import (
    GitReviewReaderAdapter,
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
from pr_auto_reviewer.infrastructure.fragments.monolithic_review_prompt_adapter import (
    MonolithicReviewPromptAdapter,
)
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)
from pr_auto_reviewer.infrastructure.fragments.repositories import (
    FileSystemFragmentRepository,
)
from pr_auto_reviewer.infrastructure.git_platform.review_context_factory import (
    ReviewContextFactory,
)
from pr_auto_reviewer.infrastructure.fragments.renderers import (
    Jinja2Renderer,
)
from pr_auto_reviewer.infrastructure.llm.prompt_mode import PromptMode
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider
from pr_auto_reviewer.infrastructure.git_platform.multi_platform import (
    CompositeRepoLister,
    CompositePrLister,
    CompositeReviewPublisher,
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
from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.application.ports.outbound.pull_request_repository import (
    PullRequestRepository,
)
from pr_auto_reviewer.application.ports.outbound.repository_context_port import (
    RepositoryContextPort,
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
from pr_auto_reviewer.application.ports.outbound.review_context_factory_port import (
    ReviewContextFactoryPort,
)
from pr_auto_reviewer.application.ports.outbound.fragment_repository_port import (
    FragmentRepositoryPort,
)
from pr_auto_reviewer.application.ports.outbound.prompt_renderer_port import (
    PromptRendererPort,
)
from pr_auto_reviewer.presentation.ports import PrListerPort, RepoListerPort


class Container:
    """Owns and provides all infrastructure-layer dependencies.

    Created eagerly — all adapters and clients are instantiated at
    construction time.  Immutable after ``__init__`` returns.
    """

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or load_config()

        logger.debug(
            "Container config: output_mode=%s, llm=%s:%s, api=%s",
            self._config.output_mode,
            self._config.llm_host, self._config.llm_model,
            self._config.platform_api_url,
        )

        is_terminal = self._config.output_mode == "terminal"
        is_both = self._config.platform_mode == GitProvider.BOTH

        if is_both:
            gb_client = GitPlatformHttpClient(
                "https://api.github.com",
                self._config.github_reviewer_token or self._config.github_token or "",
                "github",
                "owner",
            )
            cb_client = GitPlatformHttpClient(
                "https://codeberg.org/api/v1",
                self._config.codeberg_token or self._config.platform_token or "",
                "codeberg",
                "owner",
            )

            gb_reviewer = GitPlatformHttpClient(
                "https://api.github.com",
                self._config.github_reviewer_token or self._config.github_token or "",
                "github",
                "reviewer",
            )
            cb_reviewer = GitPlatformHttpClient(
                "https://codeberg.org/api/v1",
                self._config.codeberg_reviewer_token or self._config.codeberg_token or "",
                "codeberg",
                "reviewer",
            )

            self._http_client = gb_client  # default for read ops
            self._reviewer_client = gb_reviewer

            self._pr_repository: PullRequestRepository = JsonFilePullRequestRepository(_state_file_path())
            self._changeset_fetcher: ChangesetFetcherPort = GitChangesetFetcherAdapter(gb_client)
            self._repository_context: RepositoryContextPort = GitRepositoryContextAdapter(gb_client)

            self._review_publisher: ReviewPublisherPort = TerminalReviewPublisherAdapter(
                self._config.output_dest
            ) if is_terminal else CompositeReviewPublisher({
                "github": GitReviewPublisherAdapter(
                    gb_reviewer,
                    self._config.github_reviewer_token or self._config.github_token or "",
                    self._config.github_reviewer_username,
                    review_mode=self._config.github_review_mode,
                ),
                "codeberg": GitReviewPublisherAdapter(
                    cb_reviewer,
                    self._config.codeberg_reviewer_token or self._config.codeberg_token or "",
                    self._config.codeberg_reviewer_username,
                ),
            })
            self._review_reader = GitReviewReaderAdapter(gb_client)
            self._comment_reader = GitCommentReaderAdapter(gb_client)
            self._comment_publisher = GitCommentPublisherAdapter(gb_reviewer)
            self._issue_tracker = GitIssueTrackerAdapter(gb_client)

            self._repo_lister: RepoListerPort = CompositeRepoLister({
                "github": GitRepoListerAdapter(gb_client),
                "codeberg": GitRepoListerAdapter(cb_client),
            })
            self._pr_lister: PrListerPort = CompositePrLister({
                "github": GitPrListerAdapter(gb_client),
                "codeberg": GitPrListerAdapter(cb_client),
            })
        else:
            self._http_client = GitPlatformHttpClient(
                self._config.platform_api_url, self._config.platform_token, self._config.platform_mode.value, "owner",
            )
            reviewer_token = (
                self._config.reviewer_token or self._config.platform_token
            )
            self._reviewer_client = GitPlatformHttpClient(
                self._config.platform_api_url, reviewer_token, self._config.platform_mode.value, "reviewer",
            )
            self._pr_repository: PullRequestRepository = (
                NullPullRequestRepository()
                if is_terminal
                else JsonFilePullRequestRepository(_state_file_path())
            )
            logger.debug("PullRequestRepository -> %s", type(self._pr_repository).__name__)

            self._changeset_fetcher: ChangesetFetcherPort = GitChangesetFetcherAdapter(self._http_client)
            self._repository_context: RepositoryContextPort = GitRepositoryContextAdapter(self._http_client)
            self._review_publisher: ReviewPublisherPort = (
                TerminalReviewPublisherAdapter(self._config.output_dest)
                if is_terminal
                else GitReviewPublisherAdapter(
                    self._reviewer_client,
                    reviewer_token,
                    self._config.reviewer_username,
                    review_mode=self._config.github_review_mode if self._config.platform_mode == GitProvider.GITHUB else "formal",
                )
            )
            self._review_reader: ReviewReaderPort = GitReviewReaderAdapter(self._http_client)
            self._comment_reader: CommentReaderPort = GitCommentReaderAdapter(self._http_client)
            self._comment_publisher: CommentPublisherPort = GitCommentPublisherAdapter(self._reviewer_client)
            self._issue_tracker: IssueTrackerPort = GitIssueTrackerAdapter(self._http_client)
            self._pr_lister: PrListerPort = GitPrListerAdapter(self._http_client)
            self._repo_lister: RepoListerPort = GitRepoListerAdapter(self._http_client)

        self._llm_review: LlmReviewPort = OllamaLlmAdapter(
            self._config.llm_host,
            self._config.llm_model or "code-review:latest",
            max_tokens=self._config.max_prompt_tokens,
            max_file_chars=self._config.max_file_chars,
            max_files=self._config.max_files,
            max_structure_lines=self._config.max_structure_lines,
            use_compact_template=self._config.use_compact_template,
        )
        self._command_bus: CommandBusPort = InMemoryCommandBus()

        # Fragment-based prompt composition subsystem.
        # Default to bundled templates inside the package; allow
        # FRAGMENTS_DIR env override for custom fragment directories.
        _default_fragments = Path(__file__).parent / "fragments" / "templates"
        _fragments_dir_value = self._config.fragments_dir
        if _fragments_dir_value:
            _fragments_dir = Path(_fragments_dir_value)
        else:
            _fragments_dir = _default_fragments
        self._fragment_repository: FragmentRepositoryPort = (
            FileSystemFragmentRepository(_fragments_dir)
        )
        self._fragment_renderer: PromptRendererPort = Jinja2Renderer()
        self._fragment_max_tokens: int | None = getattr(
            self._config, "fragment_max_tokens", None,
        )

        # Composite port — eliminates data clump in ReviewPullRequestService
        if self._config.prompt_mode == PromptMode.MONOLITHIC:
            prompt_adapter: ComposeReviewPromptPort = MonolithicReviewPromptAdapter(
                max_total_chars=self._config.max_prompt_tokens * 4
                if self._config.max_prompt_tokens > 0
                else 60_000,
            )
        else:
            prompt_adapter = ComposeReviewPromptAdapter(
                repository=self._fragment_repository,
                renderer=self._fragment_renderer,
                max_tokens=self._fragment_max_tokens,
                max_total_chars=self._config.max_prompt_tokens * 4
                if self._config.max_prompt_tokens > 0
                else 60_000,
                use_strict_selection=getattr(self._config, "use_strict_fragment_selection", False),
            )
        self._review_context_factory: ReviewContextFactoryPort = (
            ReviewContextFactory(
                repository_context=self._repository_context,
                compose_review_prompt=prompt_adapter,
            )
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
