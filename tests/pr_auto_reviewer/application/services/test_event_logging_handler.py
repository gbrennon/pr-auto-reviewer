"""Tests for EventLoggingHandler application service."""

import logging

from pr_auto_reviewer.application.services.event_logging_handler import (
    EventLoggingHandler,
)
from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
from pr_auto_reviewer.domain.agent.turn_parse_result import TurnParseResult
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.events.conversation_completed_event import (
    ConversationCompletedEvent,
)
from pr_auto_reviewer.domain.messages.events.findings_aggregated_event import (
    FindingsAggregatedEvent,
)
from pr_auto_reviewer.domain.messages.events.phase_completed_event import (
    PhaseCompletedEvent,
)
from pr_auto_reviewer.domain.messages.events.review_turn_parsed_event import (
    ReviewTurnParsedEvent,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


def _review_item() -> ReviewItem:
    return ReviewItem(
        number=1,
        severity=ItemSeverity.MINOR,
        category=IssueCategory.QUALITY,
        file_path="src/main.py",
        description="Use f-strings",
    )


class TestEventLoggingHandler:
    """Each domain event is logged at INFO level with its key fields."""

    def test_review_turn_parsed_logs_kind_and_item_count(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        event = ReviewTurnParsedEvent(
            turn_number=3,
            result=TurnParseResult(kind="verdict", raw_items=[{"file": "a.py"}]),
        )

        EventLoggingHandler().handle_review_turn_parsed(event)

        assert "Turn 3 parsed: kind=verdict items=1" in caplog.text

    def test_review_turn_parsed_without_raw_items_logs_zero(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        event = ReviewTurnParsedEvent(
            turn_number=1,
            result=TurnParseResult(kind="unparseable"),
        )

        EventLoggingHandler().handle_review_turn_parsed(event)

        assert "Turn 1 parsed: kind=unparseable items=0" in caplog.text

    def test_conversation_completed_logs_known_verdict(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        event = ConversationCompletedEvent(
            phase_result=PhaseResult(
                items=[_review_item()], llm_verdict="approved"
            )
        )

        EventLoggingHandler().handle_conversation_completed(event)

        assert (
            "Conversation completed: verdict=approved items=1" in caplog.text
        )

    def test_conversation_completed_without_verdict_logs_unknown(
        self, caplog
    ) -> None:
        caplog.set_level(logging.INFO)
        event = ConversationCompletedEvent(
            phase_result=PhaseResult(items=[])
        )

        EventLoggingHandler().handle_conversation_completed(event)

        assert "Conversation completed: verdict=unknown items=0" in caplog.text

    def test_phase_completed_logs_counts(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        event = PhaseCompletedEvent(
            phase_name="Security Review",
            phase_result=PhaseResult(items=[_review_item()]),
            total_findings=4,
        )

        EventLoggingHandler().handle_phase_completed(event)

        assert (
            "Phase 'Security Review' complete: 1 findings (total: 4)"
            in caplog.text
        )

    def test_findings_aggregated_logs_verdict_and_item_count(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        event = FindingsAggregatedEvent(
            code_review=CodeReview(
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                items=[_review_item()],
                model_used="test",
            )
        )

        EventLoggingHandler().handle_findings_aggregated(event)

        assert (
            "Findings aggregated: verdict=changes_requested items=1"
            in caplog.text
        )

    def test_findings_aggregated_with_empty_items_logs_zero(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        event = FindingsAggregatedEvent(
            code_review=CodeReview(
                verdict=ReviewVerdict.APPROVED, model_used="test"
            )
        )

        EventLoggingHandler().handle_findings_aggregated(event)

        assert "Findings aggregated: verdict=approved items=0" in caplog.text
