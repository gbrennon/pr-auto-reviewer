"""Platform adapter wiring — builds all Git-platform-specific adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.container._platform_clients import (
    PlatformClients,
)
from pr_auto_reviewer.infrastructure.forgejo.changeset_fetcher import (
    ForgejoChangesetFetcher,
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
from pr_auto_reviewer.infrastructure.forgejo.forgejo_review_publisher import (
    ForgejoReviewPublisher,
)
from pr_auto_reviewer.infrastructure.github.changeset_fetcher import (
    GithubChangesetFetcher,
)
from pr_auto_reviewer.infrastructure.github.comment_publisher import (
    GithubCommentPublisher,
)
from pr_auto_reviewer.infrastructure.github.comment_reader import (
    GithubCommentReader,
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
from pr_auto_reviewer.infrastructure.github.repository_context import (
    GithubRepositoryContext,
)
from pr_auto_reviewer.infrastructure.github.review_reader import (
    GithubReviewReader,
)
from pr_auto_reviewer.infrastructure.github.github_review_publisher import (
    GithubReviewPublisher,
)
from pr_auto_reviewer.infrastructure.review_publishers.terminal_publisher import (
    TerminalReviewPublisherAdapter,
)
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_review_publisher import (
    CompositeReviewPublisher,
)
from pr_auto_reviewer.infrastructure.git_platform.multi_platform import (
    CompositeRepoLister,
    CompositePrLister,
    CompositeChangesetFetcher,
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
) -> PlatformAdapters:
    """Build and wire all platform-specific adapters from the given clients."""

    if config.platform_mode == GitProvider.BOTH:
        gb_owner = clients.http_client
        gb_reviewer = clients.reviewer_client
        fj_owner = clients.forgejo_owner
        fj_reviewer = clients.forgejo_reviewer

        return PlatformAdapters(
            repository_context=ForgejoRepositoryContext(fj_owner),
            changeset_fetcher=CompositeChangesetFetcher(
                GithubChangesetFetcher(gb_owner),
                ForgejoChangesetFetcher(fj_owner),
                default_platform="codeberg",
            ),
            review_publisher=(
                TerminalReviewPublisherAdapter(config.output_path)
                if is_terminal
                else CompositeReviewPublisher(
                    {
                        "github": GithubReviewPublisher(
                            gb_reviewer,
                            config.github_reviewer_username,
                            owner_client=gb_owner,
                            review_mode=config.github_review_mode,
                        ),
                        "forgejo": ForgejoReviewPublisher(
                            fj_reviewer,
                            config.forgejo_reviewer_username,
                            owner_client=fj_owner,
                        ),
                    }
                )
            ),
            review_reader=GithubReviewReader(gb_owner),
            comment_reader=GithubCommentReader(gb_owner),
            comment_publisher=GithubCommentPublisher(gb_reviewer),
            issue_tracker=GithubIssueTracker(gb_owner),
            repo_lister=CompositeRepoLister(
                {
                    "github": GithubRepoLister(gb_owner),
                    "forgejo": ForgejoRepoLister(fj_owner),
                }
            ),
            pr_lister=CompositePrLister(
                {
                    "github": GithubPrLister(gb_owner),
                    "forgejo": ForgejoPrLister(fj_owner),
                }
            ),
        )

    is_github = config.platform_mode == GitProvider.GITHUB
    http_client = clients.http_client
    reviewer_client = clients.reviewer_client

    reviewer_username = (
        config.github_reviewer_username
        if is_github
        else config.forgejo_reviewer_username
    )

    return PlatformAdapters(
        repository_context=(
            GithubRepositoryContext(http_client)
            if is_github
            else ForgejoRepositoryContext(http_client)
        ),
        changeset_fetcher=(
            GithubChangesetFetcher(http_client)
            if is_github
            else ForgejoChangesetFetcher(http_client)
        ),
        review_publisher=(
            TerminalReviewPublisherAdapter(config.output_path)
            if is_terminal
            else GithubReviewPublisher(
                reviewer_client,
                reviewer_username,
                owner_client=http_client,
            )
            if is_github
            else ForgejoReviewPublisher(
                reviewer_client,
                reviewer_username,
                owner_client=http_client,
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
            GithubRepoLister(http_client)
            if is_github
            else ForgejoRepoLister(http_client)
        ),
    )
