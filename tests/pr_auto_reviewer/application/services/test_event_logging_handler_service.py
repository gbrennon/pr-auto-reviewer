"""Tests for EventLoggingHandlerService application service."""

import logging
from pathlib import Path

from pr_auto_reviewer.application.services.event_logging_handler_service import (
    EventLoggingHandlerService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.events.agent_exchange_event import (
    AgentExchangeEvent,
)
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
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.value_objects.sub_agent_role import SubAgentRole
from pr_auto_reviewer.domain.value_objects.turn_kind import TurnKind
from pr_auto_reviewer.domain.value_objects.turn_parse_result import TurnParseResult
from pr_auto_reviewer.infrastructure.conversation_logger import (
    MarkdownConversationLogger,
)


def _review_item() -> ReviewItem:
    return ReviewItem(id="id-1",
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
            result=TurnParseResult(kind=TurnKind.VERDICT, raw_items=[{"file": "a.py"}]),
        )

        EventLoggingHandlerService().handle_review_turn_parsed(event)

        assert "Turn 3 parsed: kind=verdict items=1" in caplog.text

    def test_review_turn_parsed_without_raw_items_logs_zero(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        event = ReviewTurnParsedEvent(
            turn_number=1,
            result=TurnParseResult(kind=TurnKind.UNPARSEABLE),
        )

        EventLoggingHandlerService().handle_review_turn_parsed(event)

        assert "Turn 1 parsed: kind=unparseable items=0" in caplog.text

    def test_conversation_completed_logs_known_verdict(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        event = ConversationCompletedEvent(
            phase_result=PhaseResult(
                items=[_review_item()], llm_verdict="approved"
            )
        )

        EventLoggingHandlerService().handle_conversation_completed(event)

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

        EventLoggingHandlerService().handle_conversation_completed(event)

        assert "Conversation completed: verdict=unknown items=0" in caplog.text

    def test_phase_completed_logs_counts(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        event = PhaseCompletedEvent(
            phase_name="Security Review",
            phase_result=PhaseResult(items=[_review_item()]),
            total_findings=4,
        )

        EventLoggingHandlerService().handle_phase_completed(event)

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
                reason="test reason",
                summary="test summary",
            )
        )

        EventLoggingHandlerService().handle_findings_aggregated(event)

        assert (
            "Findings aggregated: verdict=changes_requested items=1"
            in caplog.text
        )

    def test_findings_aggregated_with_empty_items_logs_zero(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        event = FindingsAggregatedEvent(
            code_review=CodeReview(
                verdict=ReviewVerdict.APPROVED, model_used="test",
                reason="test reason",
                summary="test summary",
            )
        )

        EventLoggingHandlerService().handle_findings_aggregated(event)

        assert "Findings aggregated: verdict=approved items=0" in caplog.text

    def test_agent_exchange_persists_unprefixed_phase_name(self) -> None:
        logged: dict = {}

        class _FakeExchangeLogger:
            def log_conversation(self, **kwargs) -> Path:
                logged.update(kwargs)
                return Path("/tmp/fake-transcript.md")
        event = AgentExchangeEvent(
            role=SubAgentRole.ADVISOR,
            phase_name="Bug Hunt — Diff",
            pr_identifier_service="o/r#1",
            review_session="session-1",
            messages=[],
        )

        EventLoggingHandlerService(
            exchange_logger=_FakeExchangeLogger()
        ).handle_agent_exchange(event)

        assert logged["phase_name"] == "Bug Hunt — Diff"
        assert logged["metadata"]["agent_role"] == "advisor"

    def test_advisor_exchange_transcript_shows_grade_not_verdict(
        self, tmp_path,
    ) -> None:
        event = AgentExchangeEvent(
            role=SubAgentRole.ADVISOR,
            phase_name="Bug Hunt — Diff",
            pr_identifier_service="gbrennon/pr-auto-reviewer#147",
            review_session="20260824_014537",
            messages=[],
            metadata={"grade": "okok", "feedback": "stayed on task"},
        )

        EventLoggingHandlerService(
            exchange_logger=MarkdownConversationLogger(tmp_path)
        ).handle_agent_exchange(event)

        transcript = (
            tmp_path / "gbrennon_pr-auto-reviewer_147"
            / "20260824_014537" / "01-bug-hunt-diff.md"
        )
        text = transcript.read_text()
        assert "# advisor — " in text
        assert "Grade: okok" in text
        assert "Feedback: stayed on task" in text
        assert "Verdict:" not in text