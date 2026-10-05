"""IssueCommand — a parsed user intent extracted from a PR comment."""

from dataclasses import dataclass, field

from .issue_command_action import IssueCommandAction


@dataclass(frozen=True)
class IssueCommand:
    """A parsed user intent extracted from a PR comment.

    Derived from parsing a comment body. It is a description of intent,
    not a persistent record.
    """

    comment_id: str
    item_ids: tuple[str, ...] = field(default_factory=tuple)
    action: IssueCommandAction = IssueCommandAction.CREATE_ISSUE

    def __post_init__(self) -> None:
        """Normalize mutable input and action values to immutable contracts."""
        object.__setattr__(self, "item_ids", tuple(self.item_ids))
        object.__setattr__(self, "action", IssueCommandAction(self.action))
