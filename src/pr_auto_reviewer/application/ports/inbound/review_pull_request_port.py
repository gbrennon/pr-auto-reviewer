"""ReviewPullRequestPort — inbound port for reviewing a pull request."""

from typing import Protocol

from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)


class ReviewPullRequestPort(Protocol):
    def execute(self, command: ReviewPullRequestCommand) -> None:
        ...
