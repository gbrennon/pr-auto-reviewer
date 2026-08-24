"""TurnKind — the parsed outcome category of a single conversation turn."""

from __future__ import annotations

from enum import StrEnum


class TurnKind(StrEnum):
    """The three outcomes of parsing one LLM response in a conversation.

    ``TOOL_CALL`` requests repository exploration, ``VERDICT`` carries
    the phase review conclusion, and ``UNPARSEABLE`` failed every
    parser and triggers a reprompt.
    """

    TOOL_CALL = "tool_call"
    VERDICT = "verdict"
    UNPARSEABLE = "unparseable"
