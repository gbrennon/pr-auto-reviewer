"""ReviewItem — a single actionable finding produced by the AI review."""

from dataclasses import dataclass

from ..value_objects.item_severity import ItemSeverity


@dataclass(frozen=True)
class ReviewItem:
    """A single actionable finding produced by the AI review.

    Immutable. Two items with the same fields are identical.
    The number is positional (scoped to the review), not a persistent identity.
    """

    number: int
    severity: ItemSeverity
    category: str
    file_path: str | None
    description: str
