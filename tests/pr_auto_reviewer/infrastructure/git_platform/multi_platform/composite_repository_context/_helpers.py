"""Shared helpers, fixtures, and imports for the split test modules."""

import pytest

from pr_auto_reviewer.application.ports.outbound.repository_context_port import (
    RepositoryContextPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_repository_context import (
    CompositeRepositoryContext,
)

__all__ = ['CompositeRepositoryContext', 'PullRequestId', 'RepositoryContext', 'RepositoryContextPort', '_StubRepositoryContext', 'pytest']


class _StubRepositoryContext(RepositoryContextPort):
    """Stub context fetcher that records calls and returns canned data."""

    def __init__(self, repo_context: RepositoryContext) -> None:
        self.fetch_calls: list[PullRequestId] = []
        self.fetch_target_branches: list[str] = []
        self._repo_context = repo_context

    def fetch(self, pr_id: PullRequestId, target_branch: str = "") -> RepositoryContext:
        self.fetch_calls.append(pr_id)
        self.fetch_target_branches.append(target_branch)
        return self._repo_context

    def build_fragment_context(
        self,
        repo_context: RepositoryContext,
        file_paths: list[str],
        commit_messages: list[str] | None = None,
    ) -> tuple[str, str | None]:
        return ("fragment-content", "base-sha-abc")
