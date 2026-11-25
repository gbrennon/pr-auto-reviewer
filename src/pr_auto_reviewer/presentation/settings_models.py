"""Presentation models for explicit settings management screens."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepositoryCredentialStatus:
    """Show credential source status without exposing token values."""

    repository: str
    manager_source: str
    reviewer_source: str
    manager_error: str = ""
    reviewer_error: str = ""
