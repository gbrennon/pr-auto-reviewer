"""DaemonRuntimeStateEventHandler — updates active review progress from domain events."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

from pr_auto_reviewer.application.ports.outbound.daemon_runtime_state_port import (
    DaemonRuntimeStatePort,
)
from pr_auto_reviewer.domain.messages.events.phase_completed_event import (
    PhaseCompletedEvent,
)
from pr_auto_reviewer.domain.messages.events.review_turn_parsed_event import (
    ReviewTurnParsedEvent,
)
from pr_auto_reviewer.domain.value_objects.turn_kind import TurnKind


class DaemonRuntimeStateEventHandler:
    """Consumes domain events to keep daemon telemetry synchronized."""

    def __init__(self, state_port: DaemonRuntimeStatePort) -> None:
        self._state_port = state_port

    def handle_phase_completed(self, event: PhaseCompletedEvent) -> None:
        """Update phase name and findings when a phase completes."""
        status = self._state_port.read_status()
        if status is None or status.current_review is None:
            return
        updated_review = replace(
            status.current_review,
            phase_name=event.phase_name,
        )
        self._state_port.record_status(
            replace(
                status,
                current_review=updated_review,
                updated_at=datetime.now(UTC).isoformat(),
            )
        )

    @classmethod
    def _extract_tool_details(
        cls, event: ReviewTurnParsedEvent, fallback_call: str, fallback_args: str
    ) -> tuple[str, str]:
        if event.result.kind is not TurnKind.TOOL_CALL or not event.result.tool_call:
            return fallback_call, fallback_args
        args_str = json.dumps(event.result.tool_call.arguments, default=str)
        truncated_args = args_str if len(args_str) <= 100 else args_str[:97] + "..."
        return event.result.tool_call.tool_name, truncated_args

    def handle_turn_parsed(self, event: ReviewTurnParsedEvent) -> None:
        """Update turn number and tool call details when a turn executes."""
        status = self._state_port.read_status()
        if status is None or status.current_review is None:
            return
        current = status.current_review
        tool_name, tool_args = self._extract_tool_details(
            event, current.last_tool_call, current.last_tool_args
        )
        updated_review = replace(
            current,
            current_turn=event.turn_number,
            last_tool_call=tool_name,
            last_tool_args=tool_args,
        )
        self._state_port.record_status(
            replace(
                status,
                current_review=updated_review,
                updated_at=datetime.now(UTC).isoformat(),
            )
        )
