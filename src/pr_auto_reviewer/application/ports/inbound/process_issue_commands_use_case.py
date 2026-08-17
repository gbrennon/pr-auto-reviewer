"""ProcessIssueCommandsUseCase — inbound port for scanning PR comments for issue commands."""

from typing import Protocol

from pr_auto_reviewer.domain.messages.commands.process_issue_commands_command import (
    ProcessIssueCommandsCommand,
)


class ProcessIssueCommandsUseCase(Protocol):
    def execute(self, command: ProcessIssueCommandsCommand) -> None:
        ...
