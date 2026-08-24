"""TranscriptRouting — single source of truth for peer-phase transcript routes."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.value_objects.sub_agent_role import SubAgentRole


@dataclass(frozen=True)
class PeerPhaseRoute:
    """The routing identity of one peer review phase.

    ``label`` is the human-readable phase name used across prompts,
    events, and the review plan. ``slug`` names the phase in wiring,
    and the transcript topic ordinal derives from the route's position
    in :data:`PEER_PHASE_ROUTES` (first peer phase sorts as ``01``).
    """

    slug: str
    label: str
    role: SubAgentRole


PEER_PHASE_ROUTES: tuple[PeerPhaseRoute, ...] = (
    PeerPhaseRoute(
        slug="bug-hunt-diff",
        label="Bug Hunt — Diff",
        role=SubAgentRole.ENGINEER,
    ),
    PeerPhaseRoute(
        slug="bug-hunt-branch",
        label="Bug Hunt — Branch",
        role=SubAgentRole.ENGINEER,
    ),
    PeerPhaseRoute(
        slug="architecture-review",
        label="Architecture Review",
        role=SubAgentRole.ARCHITECT,
    ),
)
