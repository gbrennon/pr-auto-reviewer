"""Container — DI container that owns all infrastructure-layer objects."""

from __future__ import annotations

import os

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
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
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
from pr_auto_reviewer.presentation.ports import PrListerPort, RepoListerPort


class Container:
    """Owns and provides all infrastructure-layer dependencies.

    Created eagerly — all adapters and clients are instantiated at
    construction time.  Immutable after ``__init__`` returns.
    """

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or load_config()

        self._http_client = GitPlatformHttpClient(
            self._config.platform_api_url, self._config.platform_token,
        )
        reviewer_token = (
            self._config.reviewer_token or self._config.platform_token
        )
        self._reviewer_client = GitPlatformHttpClient(
            self._config.platform_api_url, reviewer_token,
        )

        self._pr_repository: PullRequestRepository = (
            NullPullRequestRepository()
            if self._config.output_mode == "terminal"
            else JsonFilePullRequestRepository(_state_file_path())
        )

        self._changeset_fetcher: ChangesetFetcherPort = (
            GitChangesetFetcherAdapter(self._http_client)
        )
        self._repository_context: RepositoryContextPort = (
            GitRepositoryContextAdapter(self._http_client)
        )
        self._llm_review: LlmReviewPort = OllamaLlmAdapter(
            self._config.llm_host, self._config.llm_model or "codellama",
        )
        self._review_publisher: ReviewPublisherPort = (
            TerminalReviewPublisherAdapter()
            if self._config.output_mode == "terminal"
            else GitReviewPublisherAdapter(
                self._reviewer_client,
                reviewer_token,
                self._config.reviewer_username,
            )
        )
        self._review_reader: ReviewReaderPort = GitReviewReaderAdapter(
            self._http_client,
        )
        self._comment_reader: CommentReaderPort = GitCommentReaderAdapter(
            self._http_client,
        )
        self._comment_publisher: CommentPublisherPort = (
            GitCommentPublisherAdapter(self._reviewer_client)
        )
        self._issue_tracker: IssueTrackerPort = GitIssueTrackerAdapter(
            self._http_client,
        )
        self._command_bus: CommandBusPort = InMemoryCommandBus()

        self._repo_lister: RepoListerPort = GitRepoListerAdapter(
            client=self._http_client,
            repos_filter=os.environ.get("REPOS_FILTER"),
        )
        self._pr_lister: PrListerPort = GitPrListerAdapter(
            client=self._http_client,
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


def _state_file_path() -> str:
    config_dir = os.path.expanduser("~/.config/pr-auto-reviewer")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "state.json")
