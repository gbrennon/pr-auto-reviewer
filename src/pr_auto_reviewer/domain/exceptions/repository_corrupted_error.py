"""Raised when the PullRequestRepositoryPort data is malformed or unreadable."""

from .domain_error import DomainError


class RepositoryCorruptedError(DomainError):
    """Raised when the PullRequestRepositoryPort data is malformed or unreadable."""
