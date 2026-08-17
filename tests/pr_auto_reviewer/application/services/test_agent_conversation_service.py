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
from pr_auto_reviewer.domain.services.review_item_factory import ReviewItemFactory

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
        repo_path=Path("/repos/owner_repo_42"),
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

    def test_derive_pr_identifier_with_matching_repo(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service._derive_pr_identifier(
            Path("/repos/owner_repo_42")
        )
        assert result == "owner/repo#42"

    def test_derive_pr_identifier_without_repo(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service._derive_pr_identifier(None)
        assert result == "unknown"

    def test_derive_pr_identifier_with_non_matching_path(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service._derive_pr_identifier(Path("/some/other/path"))
        assert result == "path"

    def test_find_mentioned_file_basename_match(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service._find_mentioned_file(
            "src/client.py is the file", ["src/client.py"]
        )
        assert result == "src/client.py"

    def test_find_mentioned_file_stem_match(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service._find_mentioned_file(
            "client python file", ["src/client.py"]
        )
        assert result == "src/client.py"

    def test_find_mentioned_file_no_match(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service._find_mentioned_file(
            "other file", ["src/client.py"]
        )
        assert result == ""

    def test_find_mentioned_file_empty_text(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service._find_mentioned_file(
            "", ["src/client.py"]
        )
        assert result == ""

    def test_find_mentioned_file_empty_changed_files(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service._find_mentioned_file(
            "something", []
        )
        assert result == ""

    def test_ground_suggestion_with_valid_file(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        original_is_file = Path.is_file
        original_locate = ReviewItemFactory._locate_symbol_range
        original_read = ReviewItemFactory._read_evidence
        try:
            # Only src/client.py "exists" in the repo
            Path.is_file = lambda self: "src/client.py" in str(self)
            ReviewItemFactory._locate_symbol_range = lambda *a, **kw: "10"
            ReviewItemFactory._read_evidence = lambda *a, **kw: "some code"
            service = AgentConversationService(
                chat_port=mock_chat_port, command_bus=mock_command_bus
            )
            suggestion = {"file": "src/client.py", "description": "get_user"}
            repo_root = Path("/repos/owner_repo_42")
            changed_files = ["src/client.py"]
            result = service._ground_suggestion(suggestion, repo_root, changed_files)
            assert result is not None
            assert "file" in result or "line" in result
        finally:
            Path.is_file = original_is_file
            ReviewItemFactory._locate_symbol_range = original_locate
            ReviewItemFactory._read_evidence = original_read

    def test_ground_suggestion_with_unknown_file(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        original_is_file = Path.is_file
        original_locate = ReviewItemFactory._locate_symbol_range
        original_read = ReviewItemFactory._read_evidence
        try:
            # Only "resolve" files that exist in the repo path
            Path.is_file = lambda self: "src/client.py" in str(self)
            ReviewItemFactory._locate_symbol_range = lambda *a, **kw: None
            ReviewItemFactory._read_evidence = lambda *a, **kw: ""
            service = AgentConversationService(
                chat_port=mock_chat_port, command_bus=mock_command_bus
            )
            suggestion = {"file": "src/unknown.py", "description": "get_user"}
            repo_root = Path("/repos/owner_repo_42")
            changed_files = ["src/client.py"]
            result = service._ground_suggestion(suggestion, repo_root, changed_files)
            assert result is None
        finally:
            Path.is_file = original_is_file
            ReviewItemFactory._locate_symbol_range = original_locate
            ReviewItemFactory._read_evidence = original_read

    def test_ground_suggestion_empty_file(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        original_is_file = Path.is_file
        original_locate = ReviewItemFactory._locate_symbol_range
        original_read = ReviewItemFactory._read_evidence
        try:
            Path.is_file = lambda self: False
            ReviewItemFactory._locate_symbol_range = lambda *a, **kw: None
            ReviewItemFactory._read_evidence = lambda *a, **kw: ""
            service = AgentConversationService(
                chat_port=mock_chat_port, command_bus=mock_command_bus
            )
            suggestion = {"file": "", "description": "get_user"}
            repo_root = Path("/repos/owner_repo_42")
            changed_files = ["src/client.py"]
            result = service._ground_suggestion(suggestion, repo_root, changed_files)
            assert result is None
        finally:
            Path.is_file = original_is_file
            ReviewItemFactory._locate_symbol_range = original_locate
            ReviewItemFactory._read_evidence = original_read

    def test_log_conversation_debug_emits(
        self, mock_chat_port, mock_command_bus, caplog,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            conversation_logger=None,
        )
        phase_result = type("PhaseResult", (), {"llm_verdict": "approved", "items": []})()
        messages = [
            type("Message", (), {"role": "user", "content": "test"})() for _ in range(2)
        ]
        with caplog.at_level("DEBUG"):
            service._log_conversation_debug(
                "test_phase", messages, 2, phase_result,
            )
        assert any("Conversation:" in r.message for r in caplog.records)

    def test_log_conversation_debug_no_when_not_debug(
        self, mock_chat_port, mock_command_bus, caplog,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            conversation_logger=None,
        )
        phase_result = type("PhaseResult", (), {"llm_verdict": "approved", "items": []})()
        messages = [
            type("Message", (), {"role": "user", "content": "test"})() for _ in range(2)
        ]
        with caplog.at_level("INFO"):
            service._log_conversation_debug(
                "test_phase", messages, 2, phase_result,
            )
        assert not any("Conversation:" in r.message for r in caplog.records)

    def test_run_empty_response_then_verd(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        mock_chat_port.send.side_effect = ["", "verdict", "extra"]
        mock_command_bus.dispatch.return_value = _verdict_parse()

        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service.execute(_command(MagicMock()))

        assert result.llm_verdict == "approved"
        assert mock_chat_port.send.call_count == 3

    def test_run_unparseable_response_then_verd(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        mock_chat_port.send.side_effect = ["not json", _verdict_parse()]
        mock_command_bus.dispatch.return_value = _verdict_parse()

        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service.execute(_command(MagicMock()))

        assert result.llm_verdict == "approved"
        assert mock_chat_port.send.call_count == 2

    def test_run_tool_call_then_verd(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        tool_execution = MagicMock()
        tool_execution.execute_tool.return_value = ToolResult(
            status="success", data={"ok": True}
        )
        mock_chat_port.send.side_effect = [
            "tool_call", None, _verdict_parse(),
        ]
        mock_command_bus.dispatch.side_effect = [
            _tool_parse(),
            None,
            _verdict_parse(),
            None,
            None,
        ]

        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        result = service.execute(_command(tool_execution))

        assert result.llm_verdict == "approved"

    def test_run_max_turns_exhausted(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        tool_execution = MagicMock()
        tool_execution.execute_tool.return_value = ToolResult(
            status="success", data={"ok": True}
        )
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=2,
        )
        # Configure the command's tool_execution after service creation
        command = _command(tool_execution)
    
        try:
            service.execute(command)
            assert False, "Expected LlmUnavailableError"
        except Exception as e:
            assert "max turns" in str(e).lower() or "exceeded" in str(e).lower()

    def test_build_phase_result_with_items(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        parsed = TurnParseResult(
            kind="verdict",
            raw_items=[
                {"description": "issue", "file": "src/a.py", "line": "10", "current_code": "x"},
            ],
            metadata={"verdict": "approved", "reason": "LGTM"},
        )
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        # Mock ReviewItemFactory.create
        original_create = ReviewItemFactory.create
        ReviewItemFactory.create = lambda *a, **kw: ([], [])
        try:
            result = service._build_phase_result(parsed, Path("/tmp"), ["src/a.py"])
            assert result.items == []
        finally:
            ReviewItemFactory.create = original_create

    def test_publish_dispatches_event(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus
        )
        service._publish("test_event")
        mock_command_bus.dispatch.assert_called_once()

    def test_log_conversation_with_logger(
        self, mock_chat_port, mock_command_bus, caplog,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            conversation_logger=MagicMock(),
        )
        phase_result = type("PhaseResult", (), {
            "llm_verdict": "approved",
            "items": []
        })()
        messages = [
            type("Message", (), {"role": "user", "content": "test"})() for _ in range(1)
        ]
        with caplog.at_level("INFO"):
            service._log_conversation(
                "test_phase", messages, 1, phase_result,
                repo_path=Path("/repos/owner_repo_42"),
            )
        # ensure no crash