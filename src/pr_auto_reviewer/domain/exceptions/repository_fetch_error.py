"""Raised when cloning or fetching a repository fails."""

from .domain_error import DomainError


class RepositoryFetchError(DomainError):
    """Raised when cloning or fetching a repository fails transiently.

    Represents a temporary inability to reach or authenticate against the
    git host (network outage, SSH key rejection, host downtime). Callers
    treat this as retryable on a later cycle rather than a fatal error.
    """
