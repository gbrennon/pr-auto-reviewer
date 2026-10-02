"""ReviewItem — a single actionable finding produced by the AI review."""

from dataclasses import dataclass, field
from typing import Literal

from ..value_objects.issue_category import IssueCategory
from ..value_objects.item_severity import ItemSeverity


@dataclass(frozen=True, init=False)
class ReviewItem:
    """A single actionable finding produced by the AI review.

    Immutable. Two items with the same fields are identical.
    The *id* is a short, human-writable, conflict-free identifier (4 characters)
    that can be referenced from PR comments (e.g. ``/issue a3f2``).
    """

    severity: ItemSeverity
    category: IssueCategory
    file_path: str | None
    description: str
    line: str = field(default="", compare=False)
    id: str = field(default="")
    current_code: str = field(default="", compare=False)
    suggested_fix: str = field(default="", compare=False)
    status: Literal["open", "resolved"] = field(default="open", compare=False)

    def __init__(
        self,
        severity: ItemSeverity | str,
        category: IssueCategory | str,
        file_path: str | None,
        description: str,
        line: str = "",
        id: str = "",
        current_code: str = "",
        suggested_fix: str = "",
        status: Literal["open", "resolved"] = "open",
    ) -> None:
        object.__setattr__(self, "severity", ItemSeverity.from_value(str(severity)))
        object.__setattr__(self, "category", IssueCategory.from_value(str(category)))
        object.__setattr__(self, "file_path", file_path)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "line", line)
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "current_code", current_code)
        object.__setattr__(self, "suggested_fix", suggested_fix)
        object.__setattr__(self, "status", status)
        if status not in ("open", "resolved"):
            raise ValueError("Review item status must be open or resolved")

    @property
    def is_open(self) -> bool:
        """Return whether this finding remains active in the latest review."""
        return self.status == "open"

    @property
    def is_blocking(self) -> bool:
        """Return True when this item should block a PR merge.

        Blocking conditions: CRITICAL or MAJOR severity, or SECURITY
        category regardless of severity.
        """
        if self.severity.is_blocking:
            return True
        return self.category == IssueCategory.SECURITY

    @property
    def is_open_blocking(self) -> bool:
        """Return whether this open finding blocks approval."""
        return self.is_open and self.is_blocking
