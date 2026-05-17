"""ReviewItem — a single actionable finding produced by the AI review."""

from dataclasses import dataclass, field

from ..value_objects.item_severity import ItemSeverity


@dataclass(frozen=True)
class ReviewItem:
    """A single actionable finding produced by the AI review.

    Immutable. Two items with the same fields are identical.
    The number is positional (scoped to the review).  The *id* is a
    short, human-writable, conflict-free identifier (4 characters)
    that can be referenced from PR comments (e.g. ``/issue a3f2``).
    """

    number: int
    severity: ItemSeverity
    category: str
    file_path: str | None
    description: str
    line: str = field(default="", compare=False)
    id: str = field(default="", compare=False)
    current_code: str = field(default="", compare=False)
    suggested_fix: str = field(default="", compare=False)
