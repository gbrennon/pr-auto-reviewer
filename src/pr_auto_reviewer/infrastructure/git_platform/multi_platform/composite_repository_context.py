"""CompositeRepositoryContext — dispatches repository-context operations by platform prefix."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.repository_context_port import (
    RepositoryContextPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext

from ._parse_platform_prefix import split_repository_prefix


class CompositeRepositoryContext(RepositoryContextPort):
    """Strips the platform prefix from *pr_id.repository* and delegates
    to the correct platform-specific ``RepositoryContextPort``."""

    def __init__(self, contexts: dict[str, RepositoryContextPort]) -> None:
        self._contexts = contexts

    def fetch(self, pr_id: PullRequestId, target_branch: str = "") -> RepositoryContext:
        platform, clean_pr_id = self._dispatch(pr_id)
        return self._contexts[platform].fetch(clean_pr_id, target_branch=target_branch)

    def build_fragment_context(
        self,
        repo_context: RepositoryContext,
        file_paths: list[str],
        commit_messages: list[str] | None = None,
    ) -> tuple[str, str | None]:
        # build_fragment_context does NOT take a pr_id — it operates on an
        # already-fetched RepositoryContext.  Delegate to the forgejo variant
        # since the serialisation logic is identical across platforms.
        return self._contexts["forgejo"].build_fragment_context(
            repo_context, file_paths, commit_messages,
        )

    def _dispatch(self, pr_id: PullRequestId) -> tuple[str, PullRequestId]:
        """Return (platform, clean_pr_id) or raise ValueError."""
        platform, clean_repo = split_repository_prefix(pr_id.repository)
        if platform not in self._contexts:
            raise ValueError(
                f"No repository context for platform: {platform}"
            )
        return platform, PullRequestId(
            repository=clean_repo, number=pr_id.number,
        )
