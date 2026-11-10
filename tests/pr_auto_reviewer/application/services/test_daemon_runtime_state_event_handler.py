from __future__ import annotations

from unittest.mock import MagicMock

from pr_auto_reviewer.application.services.daemon_runtime_state_event_handler import (
    DaemonRuntimeStateEventHandler,
)
from pr_auto_reviewer.domain.messages.events.phase_completed_event import (
    PhaseCompletedEvent,
)
from pr_auto_reviewer.domain.messages.events.review_turn_parsed_event import (
    ReviewTurnParsedEvent,
)
from pr_auto_reviewer.domain.value_objects.active_review_progress import (
    ActiveReviewProgress,
)
from pr_auto_reviewer.domain.value_objects.daemon_runtime_status import (
    DaemonRuntimeStatus,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState
from pr_auto_reviewer.domain.value_objects.tool_call import ToolCall
from pr_auto_reviewer.domain.value_objects.turn_kind import TurnKind
from pr_auto_reviewer.domain.value_objects.turn_parse_result import (
    TurnParseResult,
)


class TestDaemonRuntimeStateEventHandler:
    """Verifies event handler updates active review progress on domain events."""

    def test_updates_phase_on_phase_completed_event(self) -> None:
        state_port = MagicMock()
        status = DaemonRuntimeStatus(
            pid=123,
            daemon_mode=True,
            state=DaemonState.REVIEWING,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=600,
            allowed_repositories=("owner/repo",),
            current_review=ActiveReviewProgress(
                repository="owner/repo",
                pr_number=42,
                pr_title="PR title",
                head_sha="sha123",
                started_at="2026-11-09T18:00:00Z",
            ),
        )
        state_port.read_status.return_value = status
        handler = DaemonRuntimeStateEventHandler(state_port)
        event = PhaseCompletedEvent(
            phase_name="Bug Hunt",
            phase_result=MagicMock(),
            total_findings=2,
        )

        handler.handle_phase_completed(event)

        assert state_port.record_status.called
        recorded = state_port.record_status.call_args[0][0]
        assert recorded.current_review.phase_name == "Bug Hunt"

    def test_updates_turn_and_tool_on_turn_parsed_event(self) -> None:
        state_port = MagicMock()
        status = DaemonRuntimeStatus(
            pid=123,
            daemon_mode=True,
            state=DaemonState.REVIEWING,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=600,
            allowed_repositories=("owner/repo",),
            current_review=ActiveReviewProgress(
                repository="owner/repo",
                pr_number=42,
                pr_title="PR title",
                head_sha="sha123",
                started_at="2026-11-09T18:00:00Z",
            ),
        )
        state_port.read_status.return_value = status
        handler = DaemonRuntimeStateEventHandler(state_port)
        tool = ToolCall(tool_name="read_file", arguments={"file": "foo.py"})
        event = ReviewTurnParsedEvent(
            turn_number=4,
            result=TurnParseResult(
                kind=TurnKind.TOOL_CALL,
                tool_call=tool,
            ),
        )

        handler.handle_turn_parsed(event)

        assert state_port.record_status.called
        recorded = state_port.record_status.call_args[0][0]
        assert recorded.current_review.current_turn == 4
        assert recorded.current_review.last_tool_call == "read_file"
