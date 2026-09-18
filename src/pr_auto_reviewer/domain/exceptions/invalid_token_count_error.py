"""Raised when a token count is invalid."""

from .domain_error import DomainError


class InvalidTokenCountError(DomainError):
    """Raised when a token count is negative or otherwise invalid."""
