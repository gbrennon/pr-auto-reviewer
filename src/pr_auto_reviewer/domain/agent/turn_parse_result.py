"""TurnParseResult — the outcome of parsing a single conversation turn."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
from pr_auto_reviewer.domain.agent.tool_call import ToolCall


@dataclass(frozen=True)
class TurnParseResult:
    """The parsed outcome of a single LLM response in a conversation.

    ``kind`` is one of ``"tool_call"``, ``"verdict"``, or
    ``"unparseable"``. For verdicts, ``phase_result`` carries the
    fully-built result with validated ``ReviewItem`` objects.
    ``raw_items`` and ``metadata`` carry the unvalidated extracted
    data for downstream validation.
    """

    kind: str
    tool_call: ToolCall | None = None
    phase_result: PhaseResult | None = None
    raw_items: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None
