"""RepositoryContext — supporting context passed alongside the diff to improve review quality."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RepositoryContext:
    """Supporting context passed alongside the diff to improve review quality.

    Pure input data for prompt construction. No identity, no lifecycle.
    """

    architecture_hint: str
    conventions: str | None = None
    repository_structure: str | None = None
    pr_title: str | None = None
    pr_description: str | None = None
    python_version: str | None = None
