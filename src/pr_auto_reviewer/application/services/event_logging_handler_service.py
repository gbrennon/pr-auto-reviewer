"""EventLoggingHandlerService — logs all domain events dispatched through the command bus."""

import logging
from typing import Any

from pr_auto_reviewer.application.ports.outbound.conversation_logger_port import (
    TranscriptMetadata,
)
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

logger = logging.getLogger(__name__)


class EventLoggingHandlerService:
    """Handles all domain events by logging them at INFO level.

    One handler class, registered per event type on the command bus.
    When a conversation logger is injected, support-role exchanges are
    persisted as transcripts alongside the peer conversations.
    """

    def __init__(self, exchange_logger: Any = None) -> None:
        self._exchange_logger = exchange_logger

    def handle_agent_exchange(self, event: AgentExchangeEvent) -> None:
        """Persist a support-role transcript and log a summary line."""
        if self._exchange_logger is not None:
            self._exchange_logger.log_conversation(
                phase_name=event.phase_name,
                pr_identifier_service=event.pr_identifier_service,
                messages=event.messages,
                metadata={
                    **event.metadata,
                    TranscriptMetadata.AGENT_ROLE: event.role,
                },
                review_session=event.review_session,
            )
            return
        logger.info(
            "Agent exchange: role=%s phase=%s messages=%d",
            event.role,
            event.phase_name,
            len(event.messages),
        )

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
