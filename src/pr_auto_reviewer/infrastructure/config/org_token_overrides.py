"""OrgTokenOverrides — per-organisation token overrides for all platforms."""

from __future__ import annotations

from dataclasses import dataclass, field

from pr_auto_reviewer.infrastructure.config.org_token_entry import OrgTokenEntry


@dataclass(frozen=True)
class OrgTokenOverrides:
    github: dict[str, OrgTokenEntry] = field(default_factory=dict)
    forgejo: dict[str, OrgTokenEntry] = field(default_factory=dict)
