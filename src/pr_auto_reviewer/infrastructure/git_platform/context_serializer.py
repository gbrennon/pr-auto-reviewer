"""ContextSerializer — serialises repository context + commit messages to Markdown."""

from __future__ import annotations

from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext


class ContextSerializer:
    """Serialises a ``RepositoryContext`` (and optional commit messages)
    into a Markdown-formatted string suitable for fragment-based prompt
    composition.

    Composed into ``GitRepositoryContextAdapter`` — not a private method.
    """

    def serialize(
        self,
        repo_context: RepositoryContext,
        commit_messages: list[str] | None = None,
        python_version: str | None = None,
    ) -> str | None:
        """Build a Markdown section from *repo_context* and *commit_messages*.

        Args:
            repo_context: The repository context to serialise.
            commit_messages: Optional commit messages from the PR diff.
            python_version: Optional Python-version guidance string.

        Returns:
            A ``"\\n\\n"``-joined Markdown string, or ``None`` when
            nothing meaningful can be serialised.
        """
        parts: list[str] = []

        if repo_context.architecture_hint:
            parts.append(
                f"## Architecture: {repo_context.architecture_hint}"
            )
        if repo_context.conventions:
            parts.append(f"## Conventions\n{repo_context.conventions}")
        if repo_context.repository_structure:
            parts.append(
                f"## Repository Structure\n"
                f"{repo_context.repository_structure}"
            )
        if repo_context.pr_title:
            parts.append(f"## PR Title\n{repo_context.pr_title}")
        if repo_context.pr_description:
            parts.append(
                f"## PR Description\n{repo_context.pr_description}"
            )

        if python_version:
            parts.append(python_version)

        if commit_messages:
            messages = "\n".join(f"- {msg}" for msg in commit_messages)
            parts.append(f"## Commit Messages\n{messages}")

        return "\n\n".join(parts) if parts else None
