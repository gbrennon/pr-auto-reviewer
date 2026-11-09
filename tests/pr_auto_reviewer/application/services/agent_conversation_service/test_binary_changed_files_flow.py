from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pr_auto_reviewer.application.services.agent_conversation_service import (
    AgentConversationService,
)
from pr_auto_reviewer.domain.messages.commands.run_agent_conversation_command import (
    RunAgentConversationCommand,
)
from pr_auto_reviewer.domain.value_objects.tool_call import ToolCall
from pr_auto_reviewer.domain.value_objects.turn_kind import TurnKind
from pr_auto_reviewer.domain.value_objects.turn_parse_result import (
    TurnParseResult,
)


class StubToolExecution:
    """Tool execution stub returning JSON-serializable results."""

    def execute_tool(self, tool_call: object) -> object:
        return SimpleNamespace(
            status="ok", data={"path": "src/a.py"}, error=None,
        )


class TestBinaryChangedFilesFlow:
    """End-to-end conversation flow when PR includes binary files."""

    def test_verdict_accepted_when_binary_file_unread(
        self, mock_chat_port, mock_command_bus, tmp_path: Path,
    ) -> None:
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "a.py").write_text("print('hello')\n")
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "image.gif").write_bytes(
            b"GIF89a\x97\x00\x10\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!",
        )
        mock_chat_port.send.side_effect = ["tool", "accepted", None]
        mock_command_bus.dispatch.side_effect = [
            self._tool_parse(), None,
            self._verdict_parse(), None, None,
        ]
        service = AgentConversationService(
            chat_port=mock_chat_port,
            command_bus=mock_command_bus,
            max_turns=6,
        )
        command = RunAgentConversationCommand(
            system_prompt="Review changes.",
            repo_path=tmp_path,
            changed_files=["src/a.py", "docs/image.gif"],
            tool_execution=StubToolExecution(),
            phase_name="phase",
            review_session="test-session",
        )

        result = service.execute(command)

        assert result.llm_verdict == "approved"
        assert "docs/image.gif" not in result.unread_changed_files

    def _verdict_parse(self) -> TurnParseResult:
        return TurnParseResult(
            kind=TurnKind.VERDICT,
            raw_items=[],
            metadata={
                "verdict": "approved",
                "reason": "LGTM",
                "summary": "none",
            },
        )

    def _tool_parse(self) -> TurnParseResult:
        return TurnParseResult(
            kind=TurnKind.TOOL_CALL,
            tool_call=ToolCall(
                tool_name="read_file", arguments={"file": "src/a.py"},
            ),
        )
