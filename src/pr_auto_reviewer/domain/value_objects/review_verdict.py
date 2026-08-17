"""ReviewVerdict — enumerated conclusion of a code review."""

import re
from enum import StrEnum


class ReviewVerdict(StrEnum):
    """Enumerated conclusion of a code review.

    Maps to platform-specific events (APPROVED, REQUEST_CHANGES, COMMENT)
    as an adapter concern.
    """

    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENTED = "commented"

    @classmethod
    def coerce(cls, value: object) -> ReviewVerdict | None:
        """Map free-form LLM verdict output onto the enum, or None if unknown."""
        if value is None:
            return None
        if isinstance(value, ReviewVerdict):
            return value
        raw = str(value).strip().lower()
        if not raw:
            return None
        for member in cls:
            if raw in (member.value, member.value.replace("_", " ")):
                return member
        tokens = set(re.split(r"[^a-z0-9]+", raw))
        negative = {"critical", "changes", "request", "fail", "issues",
                    "problems", "errors", "must", "needs", "incomplete",
                    "concerns"}
        positive = {"positive", "approved", "approve", "noissues",
                    "pass", "good", "clean", "acceptable"}
        if any(
            phrase in raw
            for phrase in ("no issues", "no_issues", "no critical",
                           "no_critical", "nothing wrong")
        ):
            return cls.APPROVED
        if tokens & positive:
            return cls.APPROVED
        if tokens & negative:
            return cls.CHANGES_REQUESTED
        return None
