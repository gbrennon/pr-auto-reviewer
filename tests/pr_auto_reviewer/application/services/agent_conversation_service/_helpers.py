"""Shared helpers, fixtures, and imports for the split test modules."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from pr_auto_reviewer.application.services.agent_conversation_service import (
    AgentConversationService,
)
from pr_auto_reviewer.application.services.turn_parser_service import (
    TurnParserService,
)
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.exceptions.max_turns_exceeded_error import (
    MaxTurnsExceededError,
)
from pr_auto_reviewer.domain.messages.commands.parse_review_turn_command import (
    ParseReviewTurnCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_agent_conversation_command import (
    RunAgentConversationCommand,
)
from pr_auto_reviewer.domain.services.review_item_factory import ReviewItemFactory
from pr_auto_reviewer.domain.value_objects.advisor_directive import (
    AdvisorDirective,
)
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.sub_agent_grade import (
    SubAgentGrade,
)
from pr_auto_reviewer.domain.value_objects.tool_call import ToolCall
from pr_auto_reviewer.domain.value_objects.tool_result import ToolResult
from pr_auto_reviewer.domain.value_objects.turn_kind import TurnKind
from pr_auto_reviewer.domain.value_objects.turn_parse_result import TurnParseResult
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)

EXPLORATION_DEMAND = "MUST use the exploration tools"


def _verdict_parse() -> TurnParseResult:
    """Return a no-tool-call verdict parse result."""
    return TurnParseResult(
        kind=TurnKind.VERDICT,
        raw_items=[],
        metadata={
            "verdict": "approved",
            "reason": "LGTM",
            "summary": "none",
        },
    )


def _tool_parse() -> TurnParseResult:
    """Return a read_file tool-call parse result."""
    return TurnParseResult(
        kind=TurnKind.TOOL_CALL,
        tool_call=ToolCall(
            tool_name="read_file", arguments={"file": "src/a.py"}
        ),
    )


def _command(tool_execution: Any) -> RunAgentConversationCommand:
    """Build a single-phase conversation command."""
    return RunAgentConversationCommand(
        system_prompt="Review the changes.",
        repo_path=Path("/repos/owner_repo_42"),
        changed_files=["src/a.py"],
        tool_execution=tool_execution,
        phase_name="phase",
        review_session="test-session",
    )


__all__ = ['EXPLORATION_DEMAND', 'AdvisorDirective', 'AgentConversationService', 'Any', 'ConversationMessage', 'InMemoryCommandBus', 'LlmUnavailableError', 'MagicMock', 'MaxTurnsExceededError', 'ParseReviewTurnCommand', 'Path', 'PhaseResult', 'ReviewItemFactory', 'ReviewResponseParser', 'RunAgentConversationCommand', 'SimpleNamespace', 'SubAgentGrade', 'ToolCall', 'ToolResult', 'TurnKind', 'TurnParseResult', 'TurnParserService', '_StubToolExecution', '_command', '_tool_parse', '_verdict_parse', 'annotations']


class _StubToolExecution:
    """Tool execution stub returning JSON-serializable results."""

    def execute_tool(self, tool_call):
        return SimpleNamespace(status="ok", data={"output": "stub"}, error=None)
