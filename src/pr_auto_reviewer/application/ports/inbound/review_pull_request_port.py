"""ReviewPullRequestPort — inbound port for reviewing a pull request."""

from typing import Protocol

from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.value_objects.review_execution_result import (
    ReviewExecutionResult,
)


class ReviewPullRequestPort(Protocol):
    def execute(self, command: ReviewPullRequestCommand) -> ReviewExecutionResult:
        ...
