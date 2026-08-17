"""Fake repository context provider for tests."""

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext


class FakeRepositoryContext:
    def __init__(self, ctx: RepositoryContext | None = None) -> None:
        self._ctx = ctx or RepositoryContext(architecture_hint="")
        self.fetch_calls: list[PullRequestId] = []
        self.build_fragment_context_calls: list[
            tuple[RepositoryContext, list[str], list[str] | None]
        ] = []

    def fetch(self, pr_id: PullRequestId, target_branch: str = "") -> RepositoryContext:
        self.fetch_calls.append(pr_id)
        return self._ctx

    def build_fragment_context(
        self,
        repo_context: RepositoryContext,
        file_paths: list[str],
        commit_messages: list[str] | None = None,
    ) -> tuple[str, str | None]:
        self.build_fragment_context_calls.append(
            (repo_context, file_paths, commit_messages)
        )
        language = "python"
        parts: list[str] = []
        if repo_context.architecture_hint:
            parts.append(f"## Architecture: {repo_context.architecture_hint}")
        if repo_context.conventions:
            parts.append(f"## Conventions\n{repo_context.conventions}")
        if repo_context.pr_title:
            parts.append(f"## PR Title\n{repo_context.pr_title}")
        if repo_context.pr_description:
            parts.append(f"## PR Description\n{repo_context.pr_description}")
        if commit_messages:
            messages = "\n".join(f"- {msg}" for msg in commit_messages)
            parts.append(f"## Commit Messages\n{messages}")
        serialized = "\n\n".join(parts) if parts else None
        return language, serialized