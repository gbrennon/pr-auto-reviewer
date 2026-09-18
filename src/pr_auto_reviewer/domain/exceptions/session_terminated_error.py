"""Raised when a terminated session is mutated."""

from .domain_error import DomainError


class SessionTerminatedError(DomainError):
    """Raised when a completed or failed session receives a mutation."""
