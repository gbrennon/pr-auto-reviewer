"""Raised when an API access capability is temporarily suspended."""

from __future__ import annotations

from pr_auto_reviewer.domain.exceptions.domain_error import DomainError


class ApiAccessCapabilitySuspendedError(DomainError):
    """Signal that a required API capability cannot be used yet."""

    def __init__(self, source_name: str, remaining_seconds: int) -> None:
        self.source_name = source_name
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"API capability {source_name} is suspended for "
            f"{remaining_seconds}s"
        )
