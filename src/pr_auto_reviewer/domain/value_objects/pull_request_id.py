"""PullRequestId — composite identity of a pull request within a platform."""

from dataclasses import dataclass

from ..exceptions import InvalidPullRequestIdError


@dataclass(frozen=True)
class PullRequestId:
    """Composite identity of a pull request within a platform.

    Two PullRequestIds with the same repository and number are considered equal.
    """

    repository: str
    number: int

    def __str__(self) -> str:
        return f"{self.repository}#{self.number}"

    def __post_init__(self) -> None:
        if not self.repository or not isinstance(self.repository, str):
            raise InvalidPullRequestIdError(
                "repository must be a non-empty string"
            )
        if not isinstance(self.number, int) or self.number <= 0:
            raise InvalidPullRequestIdError(
                "number must be a positive integer"
            )
