"""Raised when a CommitSha value is empty or invalid."""

from .domain_error import DomainError


class InvalidCommitShaError(DomainError):
    """Raised when a CommitSha value is empty or invalid."""
