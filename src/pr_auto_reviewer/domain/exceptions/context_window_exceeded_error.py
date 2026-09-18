"""Raised when a context window configuration exceeds its limits."""

from .domain_error import DomainError


class ContextWindowExceededError(DomainError):
    """Raised when context-window token allocation is contradictory."""
