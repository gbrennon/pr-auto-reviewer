"""ReviewItem — a single actionable finding produced by the AI review."""

from dataclasses import dataclass, field

from ..value_objects.issue_category import IssueCategory
from ..value_objects.item_severity import ItemSeverity
from ..value_objects.review_item_status import ReviewItemStatus


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
    root_cause: str = field(default="", compare=False)
    reproduction: str = field(default="", compare=False)
    acceptance_criteria: str = field(default="", compare=False)
    detection_method: str = field(default="", compare=False)
    status: ReviewItemStatus = field(
        default=ReviewItemStatus.OPEN, compare=False
    )
    status_explanation: str = field(default="", compare=False)

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
        root_cause: str = "",
        reproduction: str = "",
        acceptance_criteria: str = "",
        detection_method: str = "",
        status: ReviewItemStatus | str = ReviewItemStatus.OPEN,
        status_explanation: str = "",
    ) -> None:
        object.__setattr__(self, "severity", ItemSeverity.from_value(str(severity)))
        object.__setattr__(self, "category", IssueCategory.from_value(str(category)))
        object.__setattr__(self, "file_path", file_path)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "line", line)
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "current_code", current_code)
        object.__setattr__(self, "suggested_fix", suggested_fix)
        object.__setattr__(self, "root_cause", root_cause)
        object.__setattr__(self, "reproduction", reproduction)
        object.__setattr__(self, "acceptance_criteria", acceptance_criteria)
        object.__setattr__(self, "detection_method", detection_method)
        normalized_status = ReviewItemStatus(status)
        object.__setattr__(self, "status", normalized_status)
        object.__setattr__(self, "status_explanation", status_explanation)

    @property
    def is_active(self) -> bool:
        """Return whether this finding remains actionable."""
        return self.status.is_active

    @property
    def is_open(self) -> bool:
        """Return whether this finding remains active in the latest review."""
        return self.is_active

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
