"""Raised when the platform rejected the review publication."""

from .domain_error import DomainError


class ReviewPublishError(DomainError):
    """Raised when the platform rejected the review publication."""
