"""Review item lifecycle states."""

from enum import StrEnum


class ReviewItemStatus(StrEnum):
    """Lifecycle state of a review item."""

    CREATED = "created"
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"

    @property
    def is_active(self) -> bool:
        """Return whether this status remains actionable."""
        return self in (ReviewItemStatus.CREATED, ReviewItemStatus.OPEN)

    @property
    def is_terminal(self) -> bool:
        """Return whether this status cannot be reopened."""
        return self in (ReviewItemStatus.RESOLVED, ReviewItemStatus.DISMISSED)
