"""ReviewVerdict — enumerated conclusion of a code review."""

from enum import StrEnum


class ReviewVerdict(StrEnum):
    """Enumerated conclusion of a code review.

    Maps to platform-specific events (APPROVED, REQUEST_CHANGES, COMMENT)
    as an adapter concern.
    """

    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENTED = "commented"

