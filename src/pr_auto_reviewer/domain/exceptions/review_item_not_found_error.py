"""Raised when a ReviewItem is not found by its short ID within a review."""

from .domain_error import DomainError

class ReviewItemNotFoundError(DomainError):
    """Raised when a ReviewItem is not found by its short ID within a review."""
