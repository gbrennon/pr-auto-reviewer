"""RepositoryContextPort — fetch repo context and build fragment-ready context."""

from typing import Protocol

from ....domain.value_objects.pull_request_id import PullRequestId
from ....domain.value_objects.repository_context import RepositoryContext


class RepositoryContextPort(Protocol):
    def fetch(self, pr_id: PullRequestId) -> RepositoryContext:
        """Return the raw repository context for *pr_id*."""
        ...

    def build_fragment_context(
        self,
        repo_context: RepositoryContext,
        file_paths: list[str],
        commit_messages: list[str] | None = None,
    ) -> tuple[str, str | None]:
        """Detect language and serialise *repo_context* for fragment-based review.

        Args:
            repo_context: The repository context (already fetched).
            file_paths: Changed file paths from the diff.
            commit_messages: Optional commit messages from the PR diff
                to include in the serialised context.

        Returns:
            A ``(language, serialized_context)`` tuple.  *language* is the
            detected programming language (``"unknown"`` when no extensions
            match).  *serialized_context* is a Markdown-formatted string
            suitable for ``ReviewContext.repository_context``, or ``None``
            when the context has no meaningful fields.
        """
        ...
