"""RegisterIssuePort — inbound port for registering a review item as a tracker issue."""

from typing import Protocol

from ...commands.register_issue_command import RegisterIssueCommand

class RegisterIssuePort(Protocol):
    """Inbound port for registering a single review item as a tracker issue.

    Satisfied by any object that implements ``execute`` with a
    ``RegisterIssueCommand``.  The command carries the PR identity, the
    short issue ID extracted from the triggering comment (which contains
    the word "issue"), and the raw command text for traceability.
    """

    def execute(self, command: RegisterIssueCommand) -> None:
        ...
