"""Tests for the AgentConversationService conversation-loop guardrails."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from pr_auto_reviewer.application.services.agent_conversation_service import (
    AgentConversationService,
)
from pr_auto_reviewer.domain.agent.tool_call import ToolCall
from pr_auto_reviewer.domain.agent.tool_result import ToolResult
from pr_auto_reviewer.domain.agent.turn_parse_result import TurnParseResult
from pr_auto_reviewer.domain.messages.commands.run_agent_conversation_command import (
    RunAgentConversationCommand,
)

EXPLORATION_DEMAND = "MUST use the exploration tools"


def _verdict_parse() -> TurnParseResult:
    """Return a no-tool-call verdict parse result."""
    return TurnParseResult(
        kind="verdict",
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
        kind="tool_call",
        tool_call=ToolCall(
            tool_name="read_file", arguments={"file": "src/a.py"}
        ),
    )


def _command(tool_execution: MagicMock) -> RunAgentConversationCommand:
    """Build a single-phase conversation command."""
    return RunAgentConversationCommand(
        system_prompt="Review the changes.",
        repo_path=Path("/tmp/fake-repo"),
        changed_files=["src/a.py"],
        tool_execution=tool_execution,
        phase_name="phase",
    )


class TestConversationLoopGuardrails:
    """Guardrail behaviour of the AgentConversationService loop."""

    def test_verdict_without_tools_is_demanded_once_then_accepted(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        mock_chat_port.send.side_effect = ["first", "second"]
        mock_command_bus.dispatch.return_value = _verdict_parse()

        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service.execute(_command(MagicMock()))

        assert result.llm_verdict == "approved"
        assert mock_chat_port.send.call_count == 2
        second_messages = mock_chat_port.send.call_args_list[1][0][0]
        demand_seen = any(
            EXPLORATION_DEMAND in message.content
            for message in second_messages
        )
        assert demand_seen

    def test_verdict_after_tool_call_is_accepted_without_demand(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        mock_chat_port.send.side_effect = ["tool", "verdict"]
        mock_command_bus.dispatch.side_effect = [
            _tool_parse(),
            None,
            _verdict_parse(),
            None,
            None,
        ]
        tool_execution = MagicMock()
        tool_execution.execute_tool.return_value = ToolResult(
            status="success", data={"ok": True}
        )

        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service.execute(_command(tool_execution))

        assert result.llm_verdict == "approved"
        assert mock_chat_port.send.call_count == 2
        sent_messages = [
            message
            for call in mock_chat_port.send.call_args_list
            for message in call[0][0]
        ]
        assert not any(
            EXPLORATION_DEMAND in message.content
            for message in sent_messages
        )



