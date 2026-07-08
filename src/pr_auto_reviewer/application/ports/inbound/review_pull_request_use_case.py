"""ReviewPullRequestUseCase — inbound port for reviewing a pull request."""

from typing import Protocol

from ...commands.review_pull_request_command import ReviewPullRequestCommand

class ReviewPullRequestUseCase(Protocol):
    def execute(self, command: ReviewPullRequestCommand) -> None:
        ...
