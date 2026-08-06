"""Behavior tests for wire_platform_adapters() — verifies PlatformAdapters
dataclass is populated with the correct adapter instances for each
platform + output-mode combination."""

from __future__ import annotations
from typing import cast

import pytest

from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.container._platform_clients import (
    wire_platform_clients,
)
from pr_auto_reviewer.infrastructure.container._platform_adapters import (
    PlatformAdapters,
    wire_platform_adapters,
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
from pr_auto_reviewer.infrastructure.forgejo.pr_lister import ForgejoPrLister
from pr_auto_reviewer.infrastructure.forgejo.repo_lister import ForgejoRepoLister
from pr_auto_reviewer.infrastructure.forgejo.review_reader import (
    ForgejoReviewReader,
)
from pr_auto_reviewer.infrastructure.forgejo.forgejo_review_publisher import (
    ForgejoReviewPublisher,
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
from pr_auto_reviewer.infrastructure.github.pr_lister import GithubPrLister
from pr_auto_reviewer.infrastructure.github.repo_lister import GithubRepoLister
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
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_changeset_fetcher import (
    CompositeChangesetFetcher,
)
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_repo_lister import (
    CompositeRepoLister,
)
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_pr_lister import (
    CompositePrLister,
)
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_repository_context import (
    CompositeRepositoryContext,
)
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_review_reader import (
    CompositeReviewReader,
)
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_comment_reader import (
    CompositeCommentReader,
)
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_comment_publisher import (
    CompositeCommentPublisher,
)
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_issue_tracker import (
    CompositeIssueTracker,
)
from pr_auto_reviewer.infrastructure.local_repository.local_git_repository import (
    LocalGitRepository,
)
from pr_auto_reviewer.infrastructure.local_repository.local_repository_context import (
    LocalRepositoryContext,
)


# ── parametrized adapter type-check data ──────────────────────────────────

FORGEJO_NON_TERMINAL_TYPES = [
    ("review_publisher", ForgejoReviewPublisher),
    ("review_reader", ForgejoReviewReader),
    ("comment_reader", ForgejoCommentReader),
    ("comment_publisher", ForgejoCommentPublisher),
    ("issue_tracker", ForgejoIssueTracker),
    ("pr_lister", ForgejoPrLister),
    ("repo_lister", ForgejoRepoLister),
]

GITHUB_NON_TERMINAL_TYPES = [
    ("review_publisher", GithubReviewPublisher),
    ("review_reader", GithubReviewReader),
    ("comment_reader", GithubCommentReader),
    ("comment_publisher", GithubCommentPublisher),
    ("issue_tracker", GithubIssueTracker),
    ("pr_lister", GithubPrLister),
    ("repo_lister", GithubRepoLister),
]
BOTH_NON_TERMINAL_TYPES = [
    ("repository_context", CompositeRepositoryContext),
    ("changeset_fetcher", CompositeChangesetFetcher),
    ("review_publisher", CompositeReviewPublisher),
    ("review_reader", CompositeReviewReader),
    ("comment_reader", CompositeCommentReader),
    ("comment_publisher", CompositeCommentPublisher),
    ("issue_tracker", CompositeIssueTracker),
    ("pr_lister", CompositePrLister),
    ("repo_lister", CompositeRepoLister),
]


# ── helpers ───────────────────────────────────────────────────────────────


def _forgejo_config(**kwargs: str) -> Config:
    defaults: dict = {
        "forgejo_owner_token": "fj-own",
        "forgejo_reviewer_token": "fj-rev",
        "forgejo_reviewer_username": "fj-bot",
    }
    defaults.update(kwargs)
    return Config(env="test", platform_mode=GitProvider.FORGEJO, **defaults)


def _github_config(**kwargs: str) -> Config:
    defaults: dict = {
        "github_owner_token": "gh-own",
        "github_reviewer_token": "gh-rev",
        "github_reviewer_username": "gh-bot",
    }
    defaults.update(kwargs)
    return Config(env="test", platform_mode=GitProvider.GITHUB, **defaults)


def _both_config() -> Config:
    return Config(
        env="test",
        platform_mode=GitProvider.BOTH,
        forgejo_owner_token="fj-own",
        forgejo_reviewer_token="fj-rev",
        forgejo_reviewer_username="fj-bot",
        github_owner_token="gh-own",
        github_reviewer_token="gh-rev",
        github_reviewer_username="gh-bot",
    )


class TestWirePlatformAdapters:
    """Behavior of wire_platform_adapters(config, clients, is_terminal)."""

    @pytest.fixture
    def local_repository(self, tmp_path):
        return LocalGitRepository(tmp_path)

    # ── single-platform: forgejo, non-terminal ────────────────────────────

    @pytest.fixture
    def fj_config(self) -> Config:
        return _forgejo_config()

    @pytest.fixture
    def fj_clients(self, fj_config: Config):
        return wire_platform_clients(fj_config)

    def test_forgejo_returns_platform_adapters(
        self,
        fj_config: Config,
        fj_clients,
    ) -> None:
        result = wire_platform_adapters(fj_config, fj_clients, is_terminal=False, local_repository=self.local_repository)
        assert isinstance(result, PlatformAdapters)

    # The field names below are kept in sync with FORGEJO_NON_TERMINAL_TYPES.

    def test_forgejo_all_fields_non_null(
        self,
        fj_config: Config,
        fj_clients,
    ) -> None:
        result = wire_platform_adapters(fj_config, fj_clients, is_terminal=False, local_repository=self.local_repository)

        for attr, _ in FORGEJO_NON_TERMINAL_TYPES:
            assert getattr(result, attr) is not None, f"{attr} is None"

    @pytest.mark.parametrize("attr,expected_type", FORGEJO_NON_TERMINAL_TYPES)
    def test_forgejo_non_terminal_adapter_types(
        self,
        fj_config: Config,
        fj_clients,
        attr: str,
        expected_type: type,
    ) -> None:
        result = wire_platform_adapters(fj_config, fj_clients, is_terminal=False, local_repository=self.local_repository)
        assert isinstance(getattr(result, attr), expected_type)

    # ── single-platform: github, non-terminal ─────────────────────────────

    @pytest.fixture
    def gh_config(self) -> Config:
        return _github_config()

    @pytest.fixture
    def gh_clients(self, gh_config: Config):
        return wire_platform_clients(gh_config)

    def test_github_returns_platform_adapters(
        self,
        gh_config: Config,
        gh_clients,
    ) -> None:
        result = wire_platform_adapters(gh_config, gh_clients, is_terminal=False, local_repository=self.local_repository)
        assert isinstance(result, PlatformAdapters)

    @pytest.mark.parametrize("attr,expected_type", GITHUB_NON_TERMINAL_TYPES)
    def test_github_non_terminal_adapter_types(
        self,
        gh_config: Config,
        gh_clients,
        attr: str,
        expected_type: type,
    ) -> None:
        result = wire_platform_adapters(gh_config, gh_clients, is_terminal=False, local_repository=self.local_repository)
        assert isinstance(getattr(result, attr), expected_type)

    # ── BOTH mode ─────────────────────────────────────────────────────────

    @pytest.fixture
    def both_config(self) -> Config:
        return _both_config()

    @pytest.fixture
    def both_clients(self, both_config: Config):
        return wire_platform_clients(both_config)

    def test_both_returns_platform_adapters(
        self,
        both_config: Config,
        both_clients,
    ) -> None:
        result = wire_platform_adapters(both_config, both_clients, is_terminal=False, local_repository=self.local_repository)
        assert isinstance(result, PlatformAdapters)

    @pytest.mark.parametrize("attr,expected_type", BOTH_NON_TERMINAL_TYPES)
    def test_both_non_terminal_adapter_types(
        self,
        both_config: Config,
        both_clients,
        attr: str,
        expected_type: type,
    ) -> None:
        result = wire_platform_adapters(both_config, both_clients, is_terminal=False, local_repository=self.local_repository)
        assert isinstance(getattr(result, attr), expected_type)

    def test_both_adapter_client_identity_and_review_mode(
        self,
        both_config: Config,
        both_clients,
    ) -> None:
        result = wire_platform_adapters(both_config, both_clients, is_terminal=False, local_repository=self.local_repository)

        # Client identity on composite adapters — verify inner adapters
        repo_ctx = cast(CompositeRepositoryContext, result.repository_context)
        assert isinstance(repo_ctx._contexts["forgejo"], LocalRepositoryContext)

        review_reader = cast(CompositeReviewReader, result.review_reader)
        assert isinstance(review_reader._readers["github"], GithubReviewReader)

        comment_reader = cast(CompositeCommentReader, result.comment_reader)
        assert isinstance(comment_reader._readers["github"], GithubCommentReader)

        comment_publisher = cast(CompositeCommentPublisher, result.comment_publisher)
        assert isinstance(comment_publisher._publishers["github"], GithubCommentPublisher)

        issue_tracker = cast(CompositeIssueTracker, result.issue_tracker)
        assert isinstance(issue_tracker._trackers["github"], GithubIssueTracker)

        review_publisher = cast(CompositeReviewPublisher, result.review_publisher)
        github_publisher = review_publisher._publishers["github"]
        assert isinstance(github_publisher, GithubReviewPublisher)
        assert github_publisher._review_mode == "formal"

    def test_both_terminal_mode_all_adapter_types(
        self,
        both_config: Config,
        both_clients,
    ) -> None:
        result = wire_platform_adapters(both_config, both_clients, is_terminal=True, local_repository=self.local_repository)
        assert isinstance(result.review_publisher, TerminalReviewPublisherAdapter)
        assert isinstance(result.changeset_fetcher, CompositeChangesetFetcher)
        assert isinstance(result.repo_lister, CompositeRepoLister)
        assert isinstance(result.pr_lister, CompositePrLister)
        assert isinstance(result.review_reader, CompositeReviewReader)
        assert isinstance(result.comment_reader, CompositeCommentReader)
        assert isinstance(result.comment_publisher, CompositeCommentPublisher)
        assert isinstance(result.issue_tracker, CompositeIssueTracker)
        assert isinstance(result.repository_context, CompositeRepositoryContext)

    @pytest.mark.parametrize(
        "config_fixture,clients_fixture",
        [
            ("fj_config", "fj_clients"),
            ("gh_config", "gh_clients"),
            ("both_config", "both_clients"),
        ],
    )
    def test_terminal_review_publisher_is_terminal_type(
        self,
        request,
        config_fixture: str,
        clients_fixture: str,
    ) -> None:
        config = request.getfixturevalue(config_fixture)
        clients = request.getfixturevalue(clients_fixture)
        result = wire_platform_adapters(config, clients, is_terminal=True, local_repository=self.local_repository)
        assert isinstance(result.review_publisher, TerminalReviewPublisherAdapter)

    # ── reviewer publisher platform routing ─────────────────────────────────

    def test_forgejo_publisher_constructed_for_forgejo_config(self) -> None:
        fj_config = _forgejo_config(forgejo_reviewer_username="my-fj-bot")
        fj_clients = wire_platform_clients(fj_config)
        result = wire_platform_adapters(fj_config, fj_clients, is_terminal=False, local_repository=self.local_repository)
        assert isinstance(result.review_publisher, ForgejoReviewPublisher)

    def test_github_publisher_constructed_for_github_config(self) -> None:
        gh_config = _github_config(github_reviewer_username="my-gh-bot")
        gh_clients = wire_platform_clients(gh_config)
        result = wire_platform_adapters(gh_config, gh_clients, is_terminal=False, local_repository=self.local_repository)
        assert isinstance(result.review_publisher, GithubReviewPublisher)