"""Raised when an issue body or title is empty."""

from .domain_error import DomainError

class InvalidIssueBodyError(DomainError):
    """Raised when an issue body or title is empty."""
