"""Platform adapter wiring — builds all Git-platform-specific adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pr_auto_reviewer.domain.value_objects.clone_protocol import CloneProtocol
from pr_auto_reviewer.infrastructure.clone_url_resolvers.https_clone_url_resolver import (
    HttpsCloneUrlResolver,
)
from pr_auto_reviewer.infrastructure.clone_url_resolvers.ssh_clone_url_resolver import (
    SshCloneUrlResolver,
)
from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.container._platform_clients import (
    PlatformClients,
)
from pr_auto_reviewer.infrastructure.forgejo.comment_publisher import (
    ForgejoCommentPublisher,
)
from pr_auto_reviewer.infrastructure.forgejo.comment_reader import (
    ForgejoCommentReader,
)
from pr_auto_reviewer.infrastructure.forgejo.forgejo_review_publisher import (
    ForgejoReviewPublisher,
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
from pr_auto_reviewer.infrastructure.forgejo.review_reader import (
    ForgejoReviewReader,
)
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider
from pr_auto_reviewer.infrastructure.git_platform.multi_platform import (
    CompositeChangesetFetcher,
    CompositeCommentPublisher,
    CompositeCommentReader,
    CompositeIssueTracker,
    CompositePrLister,
    CompositeRepoLister,
    CompositeRepositoryContext,
    CompositeReviewReader,
)
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_review_publisher import (
    CompositeReviewPublisher,
)
from pr_auto_reviewer.infrastructure.github.comment_publisher import (
    GithubCommentPublisher,
)
from pr_auto_reviewer.infrastructure.github.comment_reader import (
    GithubCommentReader,
)
from pr_auto_reviewer.infrastructure.github.github_review_publisher import (
    GithubReviewPublisher,
)
from pr_auto_reviewer.infrastructure.github.issue_tracker import (
    GithubIssueTracker,
)
from pr_auto_reviewer.infrastructure.github.pr_lister import (
    GithubPrLister,
)
from pr_auto_reviewer.infrastructure.github.repo_lister import (
    GithubRepoLister,
)
from pr_auto_reviewer.infrastructure.github.review_reader import (
    GithubReviewReader,
)
from pr_auto_reviewer.infrastructure.local_repository.local_changeset_fetcher import (
    LocalChangesetFetcher,
)
from pr_auto_reviewer.infrastructure.local_repository.local_repository_context import (
    LocalRepositoryContext,
)
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyRenderer,
)
from pr_auto_reviewer.infrastructure.review_publishers.terminal_publisher import (
    TerminalReviewPublisherAdapter,
)

if TYPE_CHECKING:
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
    from pr_auto_reviewer.application.ports.outbound.local_repository_port import (
        LocalRepositoryPort,
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
    from pr_auto_reviewer.presentation.ports import PrListerPort, RepoListerPort


_BODY_TEMPLATE_DIR = (
    Path(__file__).resolve().parent.parent / "templates"
)


@dataclass
class PlatformAdapters:
    """All platform-specific adapters wired for the current config."""

    repository_context: RepositoryContextPort
    changeset_fetcher: ChangesetFetcherPort
    review_publisher: ReviewPublisherPort
    review_reader: ReviewReaderPort
    comment_reader: CommentReaderPort
    comment_publisher: CommentPublisherPort
    issue_tracker: IssueTrackerPort
    repo_lister: RepoListerPort
    pr_lister: PrListerPort

def wire_platform_adapters(
    config: Config,
    clients: PlatformClients,
    is_terminal: bool,
    local_repository: LocalRepositoryPort,
) -> PlatformAdapters:
    """Build and wire all platform-specific adapters from the given clients."""
    body_renderer = ReviewBodyRenderer(template_dir=_BODY_TEMPLATE_DIR)
    repos_filter = config.repos_filter or None
    if config.platform_mode == GitProvider.BOTH:
        gb_manager = clients.http_client
        gb_reviewer = clients.reviewer_client
        fj_manager = clients.forgejo_manager
        fj_reviewer = clients.forgejo_reviewer
        if fj_manager is None:
            raise ValueError(
                "Forgejo manager HTTP client is required in BOTH platform mode "
                "but was not configured."
            )
        if fj_reviewer is None:
            raise ValueError(
                "Forgejo reviewer HTTP client is required in BOTH platform mode "
                "but was not configured."
            )

        resolver_cls = HttpsCloneUrlResolver if config.clone_protocol == CloneProtocol.HTTPS else SshCloneUrlResolver
        changeset_fetcher: ChangesetFetcherPort = CompositeChangesetFetcher(
            LocalChangesetFetcher(local_repository, resolver_cls("github")),
            LocalChangesetFetcher(local_repository, resolver_cls("codeberg")),
        )

        return PlatformAdapters(
            repository_context=CompositeRepositoryContext(
                {
                    "github": LocalRepositoryContext(local_repository),
                    "forgejo": LocalRepositoryContext(local_repository),
                }
            ),
            changeset_fetcher=changeset_fetcher,
            review_publisher=(
                TerminalReviewPublisherAdapter(
                    body_renderer=body_renderer,
                    output_path=config.output_path,
                )
                if is_terminal
                else CompositeReviewPublisher(
                    {
                        "github": GithubReviewPublisher(
                            body_renderer=body_renderer,
                            client=gb_reviewer,
                            manager_client=gb_manager,
                            review_mode=config.github_review_mode,
                        ),
                        "forgejo": ForgejoReviewPublisher(
                            body_renderer=body_renderer,
                            client=fj_reviewer,
                            manager_client=fj_manager,
                        ),
                    }
                )
            ),
            review_reader=CompositeReviewReader(
                {
                    "github": GithubReviewReader(gb_manager),
                    "forgejo": ForgejoReviewReader(fj_manager),
                }
            ),
            comment_reader=CompositeCommentReader(
                {
                    "github": GithubCommentReader(gb_manager),
                    "forgejo": ForgejoCommentReader(fj_manager),
                }
            ),
            comment_publisher=CompositeCommentPublisher(
                {
                    "github": GithubCommentPublisher(gb_reviewer),
                    "forgejo": ForgejoCommentPublisher(fj_reviewer),
                }
            ),
            issue_tracker=CompositeIssueTracker(
                {
                    "github": GithubIssueTracker(gb_manager),
                    "forgejo": ForgejoIssueTracker(fj_manager),
                }
            ),
            repo_lister=CompositeRepoLister(
                {
                    "github": GithubRepoLister(gb_manager, repos_filter=repos_filter),
                    "forgejo": ForgejoRepoLister(fj_manager, repos_filter=repos_filter),
                }
            ),
            pr_lister=CompositePrLister(
                {
                    "github": GithubPrLister(gb_manager),
                    "forgejo": ForgejoPrLister(fj_manager),
                }
            ),
        )

    is_github = config.platform_mode == GitProvider.GITHUB
    http_client = clients.http_client
    reviewer_client = clients.reviewer_client


    platform_mode = "github" if config.platform_mode == GitProvider.GITHUB else "codeberg"
    url_resolver = (
        HttpsCloneUrlResolver(platform_mode)
        if config.clone_protocol == CloneProtocol.HTTPS
        else SshCloneUrlResolver(platform_mode)
    )
    changeset_fetcher: ChangesetFetcherPort = LocalChangesetFetcher(local_repository, url_resolver)

    return PlatformAdapters(
        repository_context=LocalRepositoryContext(local_repository),
        changeset_fetcher=changeset_fetcher,
        review_publisher=(
            TerminalReviewPublisherAdapter(
                body_renderer=body_renderer,
                output_path=config.output_path,
            )
            if is_terminal
            else GithubReviewPublisher(
                body_renderer=body_renderer,
                client=reviewer_client,
                manager_client=http_client,
            )
            if is_github
            else ForgejoReviewPublisher(
                body_renderer=body_renderer,
                client=reviewer_client,
                manager_client=http_client,
            )
        ),
        review_reader=(
            GithubReviewReader(http_client)
            if is_github
            else ForgejoReviewReader(http_client)
        ),
        comment_reader=(
            GithubCommentReader(http_client)
            if is_github
            else ForgejoCommentReader(http_client)
        ),
        comment_publisher=(
            GithubCommentPublisher(reviewer_client)
            if is_github
            else ForgejoCommentPublisher(reviewer_client)
        ),
        issue_tracker=(
            GithubIssueTracker(http_client)
            if is_github
            else ForgejoIssueTracker(http_client)
        ),
        pr_lister=(
            GithubPrLister(http_client)
            if is_github
            else ForgejoPrLister(http_client)
        ),
        repo_lister=(
            GithubRepoLister(http_client, repos_filter=repos_filter)
            if is_github
            else ForgejoRepoLister(http_client, repos_filter=repos_filter)
        ),
    )
