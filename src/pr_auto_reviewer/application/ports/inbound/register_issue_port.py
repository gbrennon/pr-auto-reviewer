"""RegisterIssuePort — inbound port for registering a review item as a tracker issue."""

from typing import Protocol

from pr_auto_reviewer.domain.entities.issue import Issue
from pr_auto_reviewer.domain.messages.commands.register_issue_command import (
    RegisterIssueCommand,
)


class RegisterIssuePort(Protocol):
    """Inbound port for registering a single review item as a tracker issue.

    Satisfied by any object that implements ``execute`` with a
    ``RegisterIssueCommand``. The command carries the PR identity and the
    short issue ID extracted from the triggering comment.
    """

    def execute(self, command: RegisterIssueCommand) -> Issue:
        ...
