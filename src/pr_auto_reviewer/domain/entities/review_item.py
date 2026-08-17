"""ReviewItem — a single actionable finding produced by the AI review."""

from dataclasses import dataclass, field

from ..value_objects.issue_category import IssueCategory
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
    category: IssueCategory
    file_path: str | None
    description: str
    line: str = field(default="", compare=False)
    id: str = field(default="", compare=False)
    current_code: str = field(default="", compare=False)
    suggested_fix: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "severity", ItemSeverity.from_value(str(self.severity)),
        )
        object.__setattr__(
            self, "category", IssueCategory.from_value(str(self.category)),
        )

    @property
    def is_blocking(self) -> bool:
        """Return True when this item should block a PR merge.

        Blocking conditions: CRITICAL or MAJOR severity, or SECURITY
        category regardless of severity.
        """
        if self.severity.is_blocking:
            return True
        return self.category == IssueCategory.SECURITY
