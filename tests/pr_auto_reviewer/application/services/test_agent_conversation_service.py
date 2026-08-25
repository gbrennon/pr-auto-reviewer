"""Tests for the AgentConversationService conversation-loop guardrails."""

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




class _StubToolExecution:
    """Tool execution stub returning JSON-serializable results."""

    def execute_tool(self, tool_call):
        return SimpleNamespace(status="ok", data={"output": "stub"}, error=None)


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


class TestConversationLoopGuardrails:
    """Guardrail behaviour of the AgentConversationService loop."""

    def test_verdict_without_tools_is_demanded_then_accepted_after_tool_call(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        mock_chat_port.send.side_effect = [
            "verdict", "tool", "accepted",
        ]
        mock_command_bus.dispatch.side_effect = [
            _verdict_parse(), None,
            _tool_parse(), None,
            _verdict_parse(), None, None,
        ]

        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        result = service.execute(_command(_StubToolExecution()))

        assert result.llm_verdict == "approved"
        assert mock_chat_port.send.call_count == 3
        second_messages = mock_chat_port.send.call_args_list[1][0][0]
        demand_seen = any(
            EXPLORATION_DEMAND in message.content
            for message in second_messages
        )
        assert demand_seen

    def test_verdict_repeated_without_tools_is_refused(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        mock_chat_port.send.side_effect = [
            "verdict", "verdict", "verdict",
        ]
        mock_command_bus.dispatch.side_effect = [
            _verdict_parse(), None,
            _verdict_parse(), None,
            _verdict_parse(), None,
        ]

        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )

        try:
            service.execute(_command(_StubToolExecution()))
            assert False, "Expected MaxTurnsExceededError"
        except MaxTurnsExceededError as e:
            assert "refused exploration" in str(e).lower()
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
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
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
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        result = service._derive_pr_identifier(
            Path("/repos/owner_repo_42")
        )
        assert result == "owner/repo#42"

    def test_derive_pr_identifier_without_repo(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        result = service._derive_pr_identifier(None)
        assert result == "unknown"

    def test_derive_pr_identifier_with_non_matching_path(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        result = service._derive_pr_identifier(Path("/some/other/path"))
        assert result == "path"

    def test_find_mentioned_file_basename_match(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        result = service._find_mentioned_file(
            "src/client.py is the file", ["src/client.py"]
        )
        assert result == "src/client.py"

    def test_find_mentioned_file_stem_match(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        result = service._find_mentioned_file(
            "client python file", ["src/client.py"]
        )
        assert result == "src/client.py"

    def test_find_mentioned_file_no_match(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        result = service._find_mentioned_file(
            "other file", ["src/client.py"]
        )
        assert result == ""

    def test_find_mentioned_file_empty_text(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        result = service._find_mentioned_file(
            "", ["src/client.py"]
        )
        assert result == ""

    def test_find_mentioned_file_empty_changed_files(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        result = service._find_mentioned_file(
            "something", []
        )
        assert result == ""

    def test_log_conversation_debug_emits(
        self, mock_chat_port, mock_command_bus, caplog,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            conversation_logger=None,
            max_turns=10,
        )
        phase_result = PhaseResult(items=[], llm_verdict="approved")
        messages = [
            ConversationMessage(role="user", content="test") for _ in range(2)
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
            max_turns=10,
        )
        phase_result = PhaseResult(items=[], llm_verdict="approved")
        messages = [
            ConversationMessage(role="user", content="test") for _ in range(2)
        ]
        service._log_conversation_debug(
            "test-phase", messages, 1, phase_result,
        )
        assert not any("Conversation:" in r.message for r in caplog.records)

    def test_run_empty_response_then_verd(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        mock_chat_port.send.side_effect = [
            "", "tool", "verdict",
        ]
        mock_command_bus.dispatch.side_effect = [
            _tool_parse(), None,
            _verdict_parse(), None, None,
        ]

        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        result = service.execute(_command(_StubToolExecution()))

        assert result.llm_verdict == "approved"
        assert mock_chat_port.send.call_count == 3

    def test_run_unparseable_response_then_verd(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        mock_chat_port.send.side_effect = [
            "not json", "tool", "verdict",
        ]
        mock_command_bus.dispatch.side_effect = [
            _verdict_parse(), None,
            _tool_parse(), None,
            _verdict_parse(), None, None,
        ]

        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        result = service.execute(_command(_StubToolExecution()))

        assert result.llm_verdict == "approved"
        assert mock_chat_port.send.call_count == 3
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
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
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
        command = _command(tool_execution)
    
        try:
            service.execute(command)
            assert False, "Expected LlmUnavailableError"
        except LlmUnavailableError as e:
            assert "max turns" in str(e).lower() or "exceeded" in str(e).lower()

    def test_build_phase_result_with_items(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        parsed = TurnParseResult(
            kind=TurnKind.VERDICT,
            raw_items=[
                {"description": "issue", "file": "src/a.py", "line": "10", "current_code": "x"},
            ],
            metadata={"verdict": "approved", "reason": "LGTM"},
        )
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        # Mock ReviewItemFactory.create
        original_create = ReviewItemFactory.create
        ReviewItemFactory.create = lambda *a, **kw: ([], [])
        try:
            result = service._build_phase_result(parsed, Path("/tmp"), ["src/a.py"])
            assert result.items == []
        finally:
            ReviewItemFactory.create = original_create

    def test_build_phase_result_does_not_demote_rejected_items_to_suggestions(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        """Rejected raw items stay out of suggestions; only explicit LLM suggestions pass through."""
        parsed = TurnParseResult(
            kind=TurnKind.VERDICT,
            raw_items=[
                {"description": "rejected issue", "file": "src/a.py", "line": "10", "current_code": "x"},
            ],
            metadata={
                "verdict": "approved",
                "reason": "LGTM",
                "suggestions": [{"description": "real suggestion"}],
            },
        )
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        original_create = ReviewItemFactory.create
        ReviewItemFactory.create = lambda *a, **kw: ([], [])
        try:
            result = service._build_phase_result(
                parsed, Path("/tmp"), ["src/a.py"]
            )
            assert [s["description"] for s in result.llm_suggestions] == [
                "real suggestion"
            ]
        finally:
            ReviewItemFactory.create = original_create

    def test_publish_dispatches_event(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        service._publish("test_event")
        mock_command_bus.dispatch.assert_called_once()

    def test_log_conversation_with_logger(
        self, mock_chat_port, mock_command_bus, caplog,
    ) -> None:
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            conversation_logger=MagicMock(),
            max_turns=10,
        )
        phase_result = PhaseResult(items=[], llm_verdict="approved")
        messages = [ConversationMessage(role="user", content="test")]
        with caplog.at_level("INFO"):
            service._log_conversation(
                "test_phase", messages, 1, phase_result,
                repo_path=Path("/repos/owner_repo_42"),
            )

    def test_repeated_tool_call_is_refused_and_reprompted(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        """A repeated exact tool call is refused and does not execute again."""
        tool_execution = MagicMock()
        tool_execution.execute_tool.return_value = ToolResult(
            status="success", data={"ok": True}
        )
        repeated = ToolCall(
            tool_name="read_file", arguments={"file": "src/a.py"}
        )
        repeated_parse = TurnParseResult(
            kind=TurnKind.TOOL_CALL, tool_call=repeated,
        )
        mock_chat_port.send.side_effect = [
            "first", "second", "third", "verdict",
        ]
        mock_command_bus.dispatch.side_effect = [
            repeated_parse,
            None,
            repeated_parse,
            None,
            _verdict_parse(),
            None,
            None,
        ]

        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        )
        result = service.execute(_command(tool_execution))

        assert result.llm_verdict == "approved"
        # Duplicate call never reaches the executor
        assert tool_execution.execute_tool.call_count == 1
        refusal_seen = any(
            "You already ran that exact tool call" in message.content
            for call in mock_chat_port.send.call_args_list
            for message in call[0][0]
        )
        assert refusal_seen

    def test_verdict_nudged_once_after_tool_budget(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        """At the tool budget the model is nudged to conclude, once."""
        tool_execution = MagicMock()
        tool_execution.execute_tool.return_value = ToolResult(
            status="success", data={"ok": True}
        )
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=30,
        )
        # Budget is 8 tool calls; use 8 DISTINCT calls so none are refused.
        tool_parses = [
            TurnParseResult(
                kind=TurnKind.TOOL_CALL,
                tool_call=ToolCall(
                    tool_name="read_file",
                    arguments={"file": f"src/file_{i}.py"},
                ),
            )
            for i in range(8)
        ]
        sends = [f"tool-{i}" for i in range(8)] + ["verdict"]
        mock_chat_port.send.side_effect = sends
        mock_command_bus.dispatch.side_effect = (
            [item for tp in tool_parses for item in (tp, None)]
            + [_verdict_parse(), None, None]
        )

        result = service.execute(_command(tool_execution))

        assert result.llm_verdict == "approved"
        assert tool_execution.execute_tool.call_count == 8
        final_messages = mock_chat_port.send.call_args_list[-1][0][0]
        nudge_count = sum(
            "You have explored enough. Conclude now" in message.content
            for message in final_messages
        )
        assert nudge_count == 1


class TestTurnObserverWiring:
    """The advisor observes turns and blocks repeat offenders."""

    def _observer(self, grades):
                
        class _ScriptedObserver:
            def __init__(self, script):
                self._script = list(script)

            def observe(self, peer_content, phase_name, review_session, pr_identifier=""):
                return AdvisorDirective(
                    grade=SubAgentGrade.from_phrase(self._script.pop(0)),
                    feedback="off task",
                )

        return _ScriptedObserver(grades)

    def test_blocking_turn_injects_advisor_feedback(self) -> None:
        chat = MagicMock()
        chat.send.side_effect = [
            '{"action": "run_git", "args": "log --oneline -1"}',
            '{"verdict": "approved", "reason": "clean", "items": []}',
        ]
        bus = InMemoryCommandBus()
        bus.register(
            ParseReviewTurnCommand,
            TurnParserService(ReviewResponseParser()).execute,
        )
        service = AgentConversationService(
            chat_port=chat,
            command_bus=bus,
            max_turns=6,
            turn_observer=self._observer(["whatever", "okok"]),
        )
        result = service.execute(_command(_StubToolExecution()))

        assert result.llm_verdict == "approved"
        # The turn following the drifted one opens with the correction.
        post_drift_messages = chat.send.call_args_list[1][0][0]
        advisor_notes = [
            m for m in post_drift_messages
            if m.role == "user" and "ADVISOR" in m.content
        ]
        assert len(advisor_notes) == 1
        assert "off task" in advisor_notes[0].content

    def test_observer_is_not_called_on_the_final_verdict_turn(self) -> None:
        observed: list[str] = []

        class _RecordingObserver:
            def observe(self, peer_content, phase_name, review_session,
                        pr_identifier=""):
                observed.append(peer_content)
                return AdvisorDirective(grade=SubAgentGrade.OKOK)

        chat = MagicMock()
        chat.send.side_effect = [
            '{"action": "run_git", "args": "log --oneline -1"}',
            '{"verdict": "approved", "reason": "clean", "items": []}',
        ]
        bus = InMemoryCommandBus()
        bus.register(
            ParseReviewTurnCommand,
            TurnParserService(ReviewResponseParser()).execute,
        )
        service = AgentConversationService(
            chat_port=chat,
            command_bus=bus,
            max_turns=6,
            turn_observer=_RecordingObserver(),
        )

        result = service.execute(_command(_StubToolExecution()))

        assert result.llm_verdict == "approved"
        assert len(observed) == 1
        assert '"verdict"' not in observed[0]

    def test_repeated_blocks_abort_the_phase(self) -> None:
        import pytest as _pytest
        
                
        
        chat = MagicMock()
        chat.send.side_effect = [
            '{"action": "run_git", "args": "log --oneline -1"}',
            '{"action": "run_git", "args": "log --oneline -2"}',
        ]
        bus = InMemoryCommandBus()
        bus.register(
            ParseReviewTurnCommand,
            TurnParserService(ReviewResponseParser()).execute,
        )
        service = AgentConversationService(
            chat_port=chat,
            command_bus=bus,
            max_turns=6,
            turn_observer=self._observer(["don't do this!", "don't do this!"]),
            max_advisor_blocks=2,
        )

        with _pytest.raises(LlmUnavailableError, match="Advisor blocked"):
            service.execute(_command(_StubToolExecution()))


class TestCitationGrounding:
    """Praise and suggestion file citations are validated against the repo."""

    @staticmethod
    def _result_with_citations(
        metadata: dict, repo_path: Path,
    ) -> PhaseResult:
        service = AgentConversationService(
            chat_port=MagicMock(), command_bus=MagicMock(), max_turns=10,
        )
        parsed = TurnParseResult(
            kind=TurnKind.VERDICT, raw_items=[], metadata=metadata,
        )
        return service._build_phase_result(
            parsed, repo_path=repo_path, changed_files=[],
        )

    def test_praise_citing_nonexistent_file_is_dropped(
        self, tmp_path,
    ) -> None:
        result = self._result_with_citations({
            "verdict": "approved",
            "praise": [
                {
                    "file": "adapters/shallow_inbound.py",
                    "description": "great adapter",
                },
            ],
        }, repo_path=tmp_path)

        assert result.llm_praise == []

    def test_praise_citing_real_file_survives(self, tmp_path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("x = 1\n")
        result = self._result_with_citations({
            "verdict": "approved",
            "praise": [
                {
                    "file": "src/a.py",
                    "description": "clean module",
                },
            ],
        }, repo_path=tmp_path)

        assert len(result.llm_praise) == 1
        assert result.llm_praise[0]["file"] == "src/a.py"

    def test_suggestion_with_drifted_path_empties_file_keeps_prose(
        self, tmp_path,
    ) -> None:
        result = self._result_with_citations({
            "verdict": "approved",
            "suggestions": [
                {
                    "file": "ports/app_inbound.py",
                    "description": "add explicit interface definitions",
                },
            ],
        }, repo_path=tmp_path)

        assert len(result.llm_suggestions) == 1
        assert result.llm_suggestions[0]["file"] == ""
        assert (
            result.llm_suggestions[0]["description"]
            == "add explicit interface definitions"
        )

    def test_praise_citing_existing_file_outside_repo_is_dropped(
        self, tmp_path,
    ) -> None:
        outside = tmp_path.parent / (
            "outside-" + tmp_path.name
        )
        outside.mkdir()
        (outside / "secret.py").write_text("x = 1\n")

        result = self._result_with_citations({
            "verdict": "approved",
            "praise": [
                {
                    "file": str(outside / "secret.py"),
                    "description": "great module",
                },
            ],
        }, repo_path=tmp_path)

        assert result.llm_praise == []

    def test_praise_citing_parent_escape_path_is_dropped(
        self, tmp_path,
    ) -> None:
        (tmp_path.parent / "escape-target.py").write_text("x = 1\n")

        result = self._result_with_citations({
            "verdict": "approved",
            "praise": [
                {
                    "file": "../escape-target.py",
                    "description": "great module",
                },
            ],
        }, repo_path=tmp_path)

        assert result.llm_praise == []

