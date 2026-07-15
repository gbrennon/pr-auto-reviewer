"""TokenDefaults — default token values for per-org token resolution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenDefaults:
    """Default tokens used when no org-specific override is set."""

    owner_token: str = ""
    reviewer_token: str = ""
    reviewer_username: str = ""
