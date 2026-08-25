"""Tests for ConversationGuardrails and ConversationDecision."""

from __future__ import annotations

from pr_auto_reviewer.domain.value_objects.conversation_decision import (
    ConversationDecision,
)
from pr_auto_reviewer.domain.value_objects.conversation_guardrails import (
    ConversationGuardrails,
)


class TestConversationGuardrails:
    """ConversationGuardrails policy: turn budget, failure counters, tool-call tracking, verdict judgement."""

    def test_default_limit_preferences(self) -> None:
        guardrails = ConversationGuardrails()
        assert guardrails.max_turns == 10
        assert guardrails.max_empty_responses == 3
        assert guardrails.max_unparseable_responses == 3
        assert guardrails.max_tool_calls == 8
        assert guardrails.max_demands == 2
        assert guardrails.demands_issued == 0
        assert guardrails.turn == 0
        assert guardrails.consecutive_empty == 0
        assert guardrails.consecutive_unparseable == 0

    def test_has_turns_remaining_is_true_before_budget_exhausted(self) -> None:
        assert ConversationGuardrails(turn=0).has_turns_remaining() is True

    def test_has_turns_remaining_is_false_when_budget_exhausted(self) -> None:
        assert ConversationGuardrails(turn=10).has_turns_remaining() is False

    def test_advance_turn_increments_turn(self) -> None:
        assert ConversationGuardrails(turn=3).advance_turn().turn == 4

    def test_advance_turn_does_not_mutate_original(self) -> None:
        original = ConversationGuardrails(turn=3)
        original.advance_turn()
        assert original.turn == 3

    def test_mark_consecutive_success_resets_both_counters(self) -> None:
        updated = ConversationGuardrails(
            consecutive_empty=2, consecutive_unparseable=1
        ).mark_consecutive_success()
        assert updated.consecutive_empty == 0
        assert updated.consecutive_unparseable == 0

    def test_empty_below_threshold_reprompts(self) -> None:
        decision, state = ConversationGuardrails().record_empty_response()
        assert decision is ConversationDecision.REPROMPT_EMPTY
        assert state.consecutive_empty == 1

    def test_empty_at_threshold_exhausts(self) -> None:
        decision, state = ConversationGuardrails(
            max_empty_responses=2, consecutive_empty=1
        ).record_empty_response()
        assert decision is ConversationDecision.EXCEEDED_EMPTY
        assert state.consecutive_empty == 2

    def test_unparseable_below_threshold_reprompts(self) -> None:
        decision, state = ConversationGuardrails().record_unparseable_response()
        assert decision is ConversationDecision.REPROMPT_UNPARSEABLE
        assert state.consecutive_unparseable == 1

    def test_unparseable_at_threshold_exhausts(self) -> None:
        decision, state = ConversationGuardrails(
            max_unparseable_responses=2, consecutive_unparseable=1
        ).record_unparseable_response()
        assert decision is ConversationDecision.EXCEEDED_UNPARSEABLE
        assert state.consecutive_unparseable == 2

    def test_record_tool_call_increments_count(self) -> None:
        assert ConversationGuardrails(tool_calls=2).record_tool_call().tool_calls == 3

    def test_record_tool_call_does_not_mutate_original(self) -> None:
        original = ConversationGuardrails(tool_calls=2)
        original.record_tool_call()
        assert original.tool_calls == 2

    def test_accepts_when_exploration_not_required(self) -> None:
        decision, state = ConversationGuardrails(
            exploration_required=False
        ).judge_verdict()
        assert decision is ConversationDecision.ACCEPT_VERDICT
        assert state.demands_issued == 0

    def test_demands_exploration_up_to_max_then_refuses(self) -> None:
        guardrails = ConversationGuardrails(max_demands=2)
        decision, guardrails = guardrails.judge_verdict()
        assert decision is ConversationDecision.DEMAND_EXPLORATION
        assert guardrails.demands_issued == 1
        decision, guardrails = guardrails.judge_verdict()
        assert decision is ConversationDecision.DEMAND_EXPLORATION
        assert guardrails.demands_issued == 2
        decision, guardrails = guardrails.judge_verdict()
        assert decision is ConversationDecision.REFUSED_EXPLORATION
        assert guardrails.demands_issued == 2

    def test_accepts_when_tool_calls_after_demand(self) -> None:
        guardrails = ConversationGuardrails(demands_issued=1, tool_calls=1)

        decision, state = guardrails.judge_verdict()

        assert decision is ConversationDecision.ACCEPT_VERDICT