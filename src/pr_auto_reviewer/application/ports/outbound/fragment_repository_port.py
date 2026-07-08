"""FragmentRepositoryPort — port for loading prompt fragments from storage."""

from __future__ import annotations

from typing import Protocol

from pr_auto_reviewer.domain.fragments.entities.prompt_fragment import PromptFragment

class FragmentRepositoryPort(Protocol):
    """Port for loading prompt fragments from storage.

    Implementations might load from filesystem, database, or a remote API.
    The protocol uses structural subtyping — any object with the three methods
    below satisfies this contract without explicit inheritance.
    """

    def find_by_language(self, language: str) -> list[PromptFragment]:
        """Return all fragments for *language*, ordered by priority descending.

        Args:
            language: Programming language (e.g. ``"python"``, ``"go"``).

        Returns:
            Fragments for the language, or an empty list if none found.
        """
        ...

    def find_universal(self) -> list[PromptFragment]:
        """Return all language-agnostic (universal) fragments.

        Returns:
            Universal fragments ordered by priority descending.  Never
            ``None`` — use an empty list when no fragments exist.
        """
        ...

    def find_by_id(self, fragment_id: str) -> PromptFragment | None:
        """Return a single fragment by its unique ID, or ``None``.

        Searches across language-specific *and* universal directories.

        Args:
            fragment_id: Unique fragment identifier.

        Returns:
            The matching :class:`PromptFragment`, or ``None``.
        """
        ...
