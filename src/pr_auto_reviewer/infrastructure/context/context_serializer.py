from __future__ import annotations

from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext

class ContextSerializer:
    def serialize(
        self,
        repo_context: RepositoryContext,
        commit_messages: list[str] | None = None,
        python_version: str | None = None,
        pep_guidance: str | None = None,
    ) -> str | None:
        parts: list[str] = []

        if repo_context.architecture_hint:
            parts.append(
                f"## Architecture: {repo_context.architecture_hint}"
            )
        if repo_context.conventions:
            parts.append(f"## Conventions\n{repo_context.conventions}")
        if repo_context.pr_title:
            parts.append(f"## PR Title\n{repo_context.pr_title}")
        if repo_context.pr_description:
            parts.append(
                f"## PR Description\n{repo_context.pr_description}"
            )

        if python_version:
            parts.append(python_version)

        if pep_guidance:
            parts.append(pep_guidance)

        if commit_messages:
            messages = "\n".join(f"- {msg}" for msg in commit_messages)
            parts.append(f"## Commit Messages\n{messages}")

        return "\n\n".join(parts) if parts else None
