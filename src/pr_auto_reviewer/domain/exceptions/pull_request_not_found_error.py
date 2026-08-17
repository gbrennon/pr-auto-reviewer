"""Raised when a PullRequest aggregate is not found in the repository."""

from .domain_error import DomainError


class PullRequestNotFoundError(DomainError):
    """Raised when a PullRequest aggregate is not found in the repository."""
