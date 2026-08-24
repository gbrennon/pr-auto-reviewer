"""TurnParseResult — the outcome of parsing a single conversation turn."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .phase_result import PhaseResult
from .tool_call import ToolCall
from .turn_kind import TurnKind


@dataclass(frozen=True)
class TurnParseResult:
    """The parsed outcome of a single LLM response in a conversation.

    ``kind`` is one of :class:`TurnKind`. For verdicts,
    ``phase_result`` carries the fully-built result with validated
    ``ReviewItem`` objects. ``raw_items`` and ``metadata`` carry the
    unvalidated extracted data for downstream validation.
    """

    kind: TurnKind
    tool_call: ToolCall | None = None
    phase_result: PhaseResult | None = None
    raw_items: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None
