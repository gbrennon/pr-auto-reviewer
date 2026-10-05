"""Actions supported by review issue commands."""

from enum import StrEnum


class IssueCommandAction(StrEnum):
    """Action requested by a PR comment command."""

    CREATE_ISSUE = "create_issue"
    DISMISS = "dismiss"
