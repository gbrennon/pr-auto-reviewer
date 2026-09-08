"""PrepareIssueContentPort — inbound port for preparing issue title and body."""

from typing import Protocol

from pr_auto_reviewer.domain.messages.commands.prepare_issue_content_command import (
    PrepareIssueContentCommand,
)
from pr_auto_reviewer.domain.value_objects.issue_content import IssueContent


class PrepareIssueContentPort(Protocol):
    """Inbound port for preparing tracker issue title and body from a review item.

    Delegates to a sub-agent to formulate an issue title and markdown body
    structured with Problem, Rationale, and Acceptance Criteria, or falls
    back to deterministic issue body generation if the model fails.
    """

    def execute(self, command: PrepareIssueContentCommand) -> IssueContent:
        """Prepare tracker issue content for the given command."""
        ...
