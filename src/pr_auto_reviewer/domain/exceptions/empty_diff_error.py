"""Raised when a PR diff has no content."""

from .domain_error import DomainError


class EmptyDiffError(DomainError):
    """Raised when a PR diff has no content."""
