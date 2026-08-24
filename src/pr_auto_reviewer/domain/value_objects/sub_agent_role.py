"""SubAgentRole — the canonical name of each review sub-agent role."""

from __future__ import annotations

from enum import StrEnum


class SubAgentRole(StrEnum):
    """The role identity every sub-agent exchange carries.

    Publishers tag events with these members and the transcript
    logger routes and labels conversations by them, so the spelling
    of a role lives in exactly one place.
    """

    MANAGER = "manager"
    ADVISOR = "advisor"
    ENGINEER = "engineer"
    ARCHITECT = "architect"
    VERIFIER = "verifier"
