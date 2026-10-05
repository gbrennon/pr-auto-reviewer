"""Review item lifecycle states."""

from enum import StrEnum


class ReviewItemStatus(StrEnum):
    """Lifecycle state of a review item."""

    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
