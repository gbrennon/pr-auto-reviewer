"""Authentication profile metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthProfile:
    """Describe one authenticated identity and its credential transport."""

    profile_id: str
    provider: str
    host: str
    account: str
    transport: str
