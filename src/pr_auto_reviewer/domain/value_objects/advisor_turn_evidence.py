"""AdvisorTurnEvidence — structured facts used to grade one peer turn."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .turn_kind import TurnKind

EMPTY_TEXT = ""
NO_CLAIMS = 0


class AdvisorEvidenceKey(StrEnum):
    """Structured peer-turn fields extracted for advisor grading."""

    TOOL_PATH = "path"


@dataclass(frozen=True)
class AdvisorTurnEvidence:
    """Facts required to grade a peer turn without exposing its raw output."""

    phase_name: str
    turn_kind: TurnKind
    tool_name: str = EMPTY_TEXT
    tool_path: str = EMPTY_TEXT
    claim_count: int = NO_CLAIMS
