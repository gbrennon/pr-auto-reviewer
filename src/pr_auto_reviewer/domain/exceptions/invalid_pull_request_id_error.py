"""Raised when a PullRequestId has invalid repository or number."""

from .domain_error import DomainError


class InvalidPullRequestIdError(DomainError):
    """Raised when a PullRequestId has invalid repository or number."""
