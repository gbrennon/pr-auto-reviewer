"""ConversationGuardrails — guardrail policy and running state for an agentic review conversation."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .conversation_decision import ConversationDecision


@dataclass(frozen=True)
class ConversationGuardrails:
    """Immutable guardrail policy and running state for one agentic conversation.

    Every reprompt and termination decision is owned here so the conversation
    loop stays a thin orchestrator. All transitions are pure: each returns a
    new instance rather than mutating the current one.
    """

    max_turns: int = 10
    max_empty_responses: int = 3
    max_unparseable_responses: int = 3
    exploration_required: bool = True
    max_tool_calls: int = 8
    max_demands: int = 2

    demands_issued: int = 0
    turn: int = 0
    consecutive_empty: int = 0
    consecutive_unparseable: int = 0
    tool_calls: int = 0

    def has_turns_remaining(self) -> bool:
        """Return whether the conversation may issue another turn."""
        return self.turn < self.max_turns

    def advance_turn(self) -> ConversationGuardrails:
        """Return a new state with the turn counter incremented by one."""
        return replace(self, turn=self.turn + 1)

    def mark_consecutive_success(self) -> ConversationGuardrails:
        """Return a new state with the consecutive-failure counters reset."""
        return replace(
            self, consecutive_empty=0, consecutive_unparseable=0
        )

    def record_empty_response(
        self,
    ) -> tuple[ConversationDecision, ConversationGuardrails]:
        """Count an empty response and decide whether to reprompt or give up."""
        next_state = replace(
            self, consecutive_empty=self.consecutive_empty + 1
        )
        if next_state.consecutive_empty >= self.max_empty_responses:
            return ConversationDecision.EXCEEDED_EMPTY, next_state
        return ConversationDecision.REPROMPT_EMPTY, next_state

    def record_unparseable_response(
        self,
    ) -> tuple[ConversationDecision, ConversationGuardrails]:
        """Count an unparseable response and decide to reprompt or give up."""
        next_state = replace(
            self,
            consecutive_unparseable=self.consecutive_unparseable + 1,
        )
        if (
            next_state.consecutive_unparseable
            >= self.max_unparseable_responses
        ):
            return ConversationDecision.EXCEEDED_UNPARSEABLE, next_state
        return ConversationDecision.REPROMPT_UNPARSEABLE, next_state

    def record_tool_call(self) -> ConversationGuardrails:
        """Return a new state with the executed-tool-call count incremented."""
        return replace(self, tool_calls=self.tool_calls + 1)

    def should_force_verdict(self) -> bool:
        """Return whether the model explored enough and must conclude now.

        Guards against exploration loops: after ``max_tool_calls`` tool
        executions the phase must render a verdict instead of issuing
        more tool calls.
        """
        return self.tool_calls >= self.max_tool_calls
    def judge_verdict(
        self,
    ) -> tuple[ConversationDecision, ConversationGuardrails]:
        """Decide whether to accept a verdict or demand exploration first.

        Accepts the verdict when the model already explored the repository
        (``tool_calls > 0``) or when ``exploration_required`` is False.
        Otherwise demands exploration up to ``max_demands`` times. If the
        model refuses every demand (re-emits a verdict without any tool
        call), the phase is aborted.
        """
        if not self.exploration_required:
            return ConversationDecision.ACCEPT_VERDICT, self
        if self.tool_calls > 0:
            return ConversationDecision.ACCEPT_VERDICT, self
        if self.demands_issued >= self.max_demands:
            return ConversationDecision.REFUSED_EXPLORATION, self
        next_state = replace(
            self, demands_issued=self.demands_issued + 1,
        )
        return ConversationDecision.DEMAND_EXPLORATION, next_state
