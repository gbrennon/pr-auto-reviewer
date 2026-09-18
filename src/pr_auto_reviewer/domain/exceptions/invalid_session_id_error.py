"""Raised when a session identifier is invalid."""

from .domain_error import DomainError


class InvalidSessionIdError(DomainError):
    """Raised when a session identifier is empty or unsafe."""
