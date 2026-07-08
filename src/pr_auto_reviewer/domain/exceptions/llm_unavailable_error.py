"""Raised when the LLM port is unreachable or timed out."""

from .domain_error import DomainError

class LlmUnavailableError(DomainError):
    """Raised when the LLM port is unreachable or timed out."""
