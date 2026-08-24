"""ConversationDecision — the guardrail-driven action a conversation loop must take."""

from __future__ import annotations

from enum import StrEnum


class ConversationDecision(StrEnum):
    """The action the conversation loop must take for a parsed turn."""

    ACCEPT_VERDICT = "accept_verdict"
    DEMAND_EXPLORATION = "demand_exploration"
    REPROMPT_EMPTY = "reprompt_empty"
    REPROMPT_UNPARSEABLE = "reprompt_unparseable"
    EXCEEDED_EMPTY = "exceeded_empty"
    EXCEEDED_UNPARSEABLE = "exceeded_unparseable"
