"""Raised when the issue tracker port fails to create an issue."""

from .domain_error import DomainError


class IssueCreationError(DomainError):
    """Raised when the issue tracker port fails to create an issue."""

    def __init__(self, repository: str, item_number: int, reason: str) -> None:
        self.repository = repository
        self.item_number = item_number
        self.reason = reason
        super().__init__(
            f"Issue creation failed for #{item_number} in {repository}: {reason}"
        )
