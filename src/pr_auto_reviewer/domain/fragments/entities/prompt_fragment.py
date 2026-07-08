"""PromptFragment — immutable value object for a composable prompt fragment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class PromptFragment:
    """Immutable value object representing a prompt template fragment.

    A fragment is a reusable piece of a prompt that can be composed with
    other fragments to build a complete review prompt.  Fragments are
    identified by their ``id`` field (value-object equality).

    Universal fragments (``language is None``) apply to every review
    regardless of the target programming language.
    """

    id: str
    content: str
    language: str | None
    priority: int
    category: str
    metadata: dict[str, Any] = None

    def __post_init__(self) -> None:
        """Validate and initialise defaults after dataclass construction."""
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if self.priority < 0:
            raise ValueError("priority must be non-negative")
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})

    def is_universal(self) -> bool:
        """Return ``True`` when this fragment applies to all languages."""
        return self.language is None

    def __eq__(self, other: object) -> bool:
        """Equality based on ID only (value-object identity)."""
        if not isinstance(other, PromptFragment):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on ID only."""
        return hash(self.id)
