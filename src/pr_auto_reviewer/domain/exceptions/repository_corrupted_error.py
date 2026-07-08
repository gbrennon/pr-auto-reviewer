"""Raised when the PullRequestRepository data is malformed or unreadable."""

from .domain_error import DomainError

class RepositoryCorruptedError(DomainError):
    """Raised when the PullRequestRepository data is malformed or unreadable."""
