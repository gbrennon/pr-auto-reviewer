"""EventLoggingHandler — logs all domain events dispatched through the command bus."""

import logging

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

logger = logging.getLogger(__name__)


class EventLoggingHandler:
    """Handles all domain events by logging them at INFO level.

    One handler class, registered per event type on the command bus.
    """

    def handle_review_turn_parsed(self, event: ReviewTurnParsedEvent) -> None:
        logger.info(
            "Turn %d parsed: kind=%s items=%d",
            event.turn_number,
            event.result.kind,
            len(event.result.raw_items or []),
        )

    def handle_conversation_completed(
        self, event: ConversationCompletedEvent
    ) -> None:
        logger.info(
            "Conversation completed: verdict=%s items=%d",
            event.phase_result.llm_verdict or "unknown",
            len(event.phase_result.items),
        )

    def handle_phase_completed(self, event: PhaseCompletedEvent) -> None:
        logger.info(
            "Phase '%s' complete: %d findings (total: %d)",
            event.phase_name,
            len(event.phase_result.items),
            event.total_findings,
        )

    def handle_findings_aggregated(
        self, event: FindingsAggregatedEvent
    ) -> None:
        logger.info(
            "Findings aggregated: verdict=%s items=%d",
            event.code_review.verdict.value,
            len(event.code_review.items) if event.code_review.items else 0,
        )
