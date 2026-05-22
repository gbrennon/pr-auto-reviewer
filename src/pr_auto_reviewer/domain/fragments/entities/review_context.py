"""ReviewContext — context information for fragment-based prompt composition."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewContext:
    """Context about the code being reviewed, used to select and render fragments.

    This is distinct from the existing ``RepositoryContext`` value object
    (which carries architecture hints and conventions).  ``ReviewContext``
    carries the information needed by the fragment composition pipeline:
    the target language, changed file paths, and the diff itself.
    """

    language: str
    file_paths: list[str]
    diff: str
    repository_context: str | None = None

    def __post_init__(self) -> None:
        """Validate fields after dataclass construction."""
        if not self.language or not self.language.strip():
            raise ValueError("language cannot be empty")
        if not self.file_paths:
            raise ValueError("file_paths cannot be empty")
