"""IssueCommand — a parsed user intent extracted from a PR comment requesting issue creation."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IssueCommand:
    """A parsed user intent extracted from a PR comment requesting issue creation.

    Derived from parsing a comment body. It is a description of intent,
    not a persistent record.
    """

    comment_id: str
    item_numbers: list[int] = field(default_factory=list)
