from __future__ import annotations
from typing import Any
from pr_auto_reviewer.application.ports.outbound.changeset_fetcher_port import ChangesetFetcherPort
from pr_auto_reviewer.application.ports.outbound.repository_context_port import RepositoryContextPort
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId

class CompositeChangesetFetcher(ChangesetFetcherPort):
    """ChangesetFetcherPort that routes to the correct provider based on PR platform."""
    def __init__(self, fetchers: dict[str, ChangesetFetcherPort]) -> None:
        self._fetchers = fetchers

    def fetch_changeset(self, pr_id: PullRequestId) -> Any:
        fetcher = self._fetchers.get(pr_id.platform)
        if not fetcher:
            raise ValueError(f"No changeset fetcher for platform {pr_id.platform}")
        return fetcher.fetch_changeset(pr_id)

class CompositeRepositoryContext(RepositoryContextPort):
    """RepositoryContextPort that routes to the correct provider based on PR platform."""
    def __init__(self, contexts: dict[str, RepositoryContextPort]) -> None:
        self._contexts = contexts

    def get_context(self, pr_id: PullRequestId) -> Any:
        context = self._contexts.get(pr_id.platform)
        if not context:
            raise ValueError(f"No repository context for platform {pr_id.platform}")
        return context.get_context(pr_id)
