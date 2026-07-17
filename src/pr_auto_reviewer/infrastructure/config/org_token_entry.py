"""OrgTokenEntry — per-organisation token overrides for one org."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrgTokenEntry:
    owner_token: str = ""
    reviewer_token: str = ""
    reviewer_username: str = ""
