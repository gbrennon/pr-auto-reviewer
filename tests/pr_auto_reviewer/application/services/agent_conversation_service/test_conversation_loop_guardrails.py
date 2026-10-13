import pytest

from pr_auto_reviewer.domain.exceptions.review_budget_exhausted_error import (
    ReviewBudgetExhaustedError,
)
from ._helpers import *

_CONVERSATION_LOGGER = (
    "pr_auto_reviewer.application.services.agent_conversation_service"
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
        assert mock_chat_port.send.call_count == 4
        second_messages = mock_chat_port.send.call_args_list[1][0][0]
        demand_seen = any(
            EXPLORATION_DEMAND in message.content
            for message in second_messages
        )
        assert demand_seen

    def test_verdict_waits_for_every_readable_changed_file(
        self, mock_chat_port, mock_command_bus, tmp_path,
    ) -> None:
        first_file = tmp_path / "first.py"
        second_file = tmp_path / "second.py"
        first_file.write_text("first = True\n")
        second_file.write_text("second = True\n")
        command = RunAgentConversationCommand(
            system_prompt="Review the changes.",
            repo_path=tmp_path,
            changed_files=["first.py", "second.py"],
            tool_execution=MagicMock(),
            phase_name="phase",
            review_session="test-session",
        )
        first_tool = ToolCall(
            tool_name="read_file", arguments={"file": "first.py"}
        )
        second_tool = ToolCall(
            tool_name="read_file", arguments={"file": "second.py"}
        )
        mock_chat_port.send.side_effect = [
            "first tool", "verdict", "second tool", "verdict", None,
        ]
        mock_command_bus.dispatch.side_effect = [
            TurnParseResult(kind=TurnKind.TOOL_CALL, tool_call=first_tool),
            None,
            _verdict_parse(),
            None,
            TurnParseResult(kind=TurnKind.TOOL_CALL, tool_call=second_tool),
            None,
            _verdict_parse(),
            None,
            None,
        ]
        command.tool_execution.execute_tool.side_effect = [
            ToolResult(status="ok", data={"path": "first.py"}),
            ToolResult(status="ok", data={"path": "second.py"}),
        ]

        result = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        ).execute(command)

        assert result.read_file_paths == ("first.py", "second.py")
        assert result.unread_changed_files == ()
        demand_seen = any(
            "second.py" in message.content
            for call in mock_chat_port.send.call_args_list
            for message in call[0][0]
        )
        assert demand_seen

    def test_verdict_requires_only_explicit_coverage_files(
        self, mock_chat_port, mock_command_bus, tmp_path,
    ) -> None:
        first_file = tmp_path / "first.py"
        second_file = tmp_path / "second.py"
        first_file.write_text("first = True\n")
        second_file.write_text("second = True\n")
        command = RunAgentConversationCommand(
            system_prompt="Review the changes.",
            repo_path=tmp_path,
            changed_files=["first.py", "second.py"],
            coverage_files=(),
            tool_execution=MagicMock(),
            phase_name="phase",
            review_session="test-session",
        )
        first_tool = ToolCall(
            tool_name="read_file", arguments={"file": "first.py"}
        )
        mock_chat_port.send.side_effect = ["first tool", "verdict", None]
        mock_command_bus.dispatch.side_effect = [
            TurnParseResult(kind=TurnKind.TOOL_CALL, tool_call=first_tool),
            None,
            _verdict_parse(),
            None,
            None,
        ]
        command.tool_execution.execute_tool.return_value = ToolResult(
            status="ok", data={"path": "first.py"},
        )

        result = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        ).execute(command)

        assert result.llm_verdict == "approved"
        assert result.read_file_paths == ("first.py",)
        assert result.unread_changed_files == ("second.py",)

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
        assert mock_chat_port.send.call_count == 3
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
        with caplog.at_level("DEBUG", logger=_CONVERSATION_LOGGER):
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
        with caplog.at_level("INFO", logger=_CONVERSATION_LOGGER):
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
        assert mock_chat_port.send.call_count == 4

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
        assert mock_chat_port.send.call_count == 4
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
            "first", "second", "third",
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

    def test_repeated_tool_call_streak_aborts_without_progress(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        """A repeated-call loop stops after three calls without progress."""
        tool_execution = MagicMock()
        tool_execution.execute_tool.return_value = ToolResult(
            status="success", data={"path": "src/a.py"}
        )
        repeated = ToolCall(
            tool_name="read_file", arguments={"file": "src/a.py"}
        )
        repeated_parse = TurnParseResult(
            kind=TurnKind.TOOL_CALL, tool_call=repeated,
        )
        mock_chat_port.send.side_effect = [
            "first", "second", "third", "fourth",
        ]
        mock_command_bus.dispatch.side_effect = [
            repeated_parse, None,
            repeated_parse, None,
            repeated_parse, None,
            repeated_parse, None,
        ]

        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=30,
        )

        with pytest.raises(ReviewBudgetExhaustedError, match="no progress"):
            service.execute(_command(tool_execution))

        assert tool_execution.execute_tool.call_count == 1

    def test_large_review_replays_repeated_read_file_calls(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        tool_execution = MagicMock()
        tool_execution.execute_tool.return_value = ToolResult(
            status="success", data={"path": "src/a.py"}
        )
        repeated = ToolCall(
            tool_name="read_file", arguments={"file": "src/a.py"}
        )
        repeated_parse = TurnParseResult(
            kind=TurnKind.TOOL_CALL, tool_call=repeated,
        )
        mock_chat_port.send.side_effect = [
            "first", "second", "third", "fourth", "verdict",
        ]
        mock_command_bus.dispatch.side_effect = [
            repeated_parse, None,
            repeated_parse, None,
            repeated_parse, None,
            repeated_parse, None,
            _verdict_parse(), None, None,
        ]
        command = RunAgentConversationCommand(
            system_prompt="Review the changes.",
            repo_path=Path("/repos/owner_repo_42"),
            changed_files=["src/a.py", "src/b.py"],
            coverage_files=(),
            tool_execution=tool_execution,
            phase_name="phase",
            review_session="test-session",
        )

        result = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=10,
        ).execute(command)

        assert result.llm_verdict == "approved"
        assert tool_execution.execute_tool.call_count == 4

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

    def test_praise_and_suggestions_preserved_when_explore_before_verdict_reprompts(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        """Praise and suggestions from an early verdict turn survive after forced exploration."""
        tool_execution = MagicMock()
        tool_execution.execute_tool.return_value = ToolResult(
            status="ok", data={"content": "file content"},
        )
        service = AgentConversationService(
            chat_port=mock_chat_port, command_bus=mock_command_bus,
            max_turns=6,
        )
        early_verdict = TurnParseResult(
            kind=TurnKind.VERDICT,
            metadata={
                "verdict": "approved",
                "praise": [{"file": "src/a.py", "description": "Good structure"}],
                "suggestions": [{"file": "src/a.py", "description": "Add docstrings"}],
            },
        )
        tool_parse = TurnParseResult(
            kind=TurnKind.TOOL_CALL,
            tool_call=ToolCall(
                tool_name="read_file",
                arguments={"file": "src/a.py"},
            ),
        )
        final_verdict = TurnParseResult(
            kind=TurnKind.VERDICT,
            metadata={
                "verdict": "approved",
                "praise": [],
                "suggestions": [],
            },
        )
        mock_chat_port.send.side_effect = [
            "verdict-early", "tool-call", "verdict-final",
        ]
        mock_command_bus.dispatch.side_effect = [
            early_verdict, None,
            tool_parse, None,
            final_verdict, None, None,
        ]

        result = service.execute(_command(tool_execution))

        assert result.llm_verdict == "approved"
        assert len(result.llm_praise) == 1
        assert result.llm_praise[0]["description"] == "Good structure"
        assert len(result.llm_suggestions) == 1
        assert result.llm_suggestions[0]["description"] == "Add docstrings"

    def test_dedicated_suggestions_and_praise_turn_populates_phase_result(
        self, mock_chat_port, mock_command_bus,
    ) -> None:
        """Dedicated turn following an accepted verdict populates suggestions and praise."""
        tool_execution = MagicMock()
        tool_execution.execute_tool.return_value = ToolResult(
            status="success", data={"ok": True}
        )
        service = AgentConversationService(
            chat_port=mock_chat_port,
            command_bus=mock_command_bus,
            max_turns=6,
        )
        tool_parse = TurnParseResult(
            kind=TurnKind.TOOL_CALL,
            tool_call=ToolCall(
                tool_name="read_file",
                arguments={"file": "src/a.py"},
            ),
        )
        verdict_parse = TurnParseResult(
            kind=TurnKind.VERDICT,
            raw_items=[],
            metadata={
                "verdict": "approved",
                "reason": "Clean code",
                "summary": "Looks good",
                "praise": [],
                "suggestions": [],
            },
        )
        suggestions_praise_parse = TurnParseResult(
            kind=TurnKind.VERDICT,
            raw_items=[],
            metadata={
                "praise": [{"file": "src/a.py", "description": "Excellent error handling"}],
                "suggestions": [{"file": "src/a.py", "description": "Reduce method complexity by composing validator class"}],
            },
        )
        mock_chat_port.send.side_effect = [
            "tool-call", "verdict", "suggestions-and-praise",
        ]
        mock_command_bus.dispatch.side_effect = [
            tool_parse, None,
            verdict_parse, None,
            suggestions_praise_parse,
            None,
        ]

        result = service.execute(_command(tool_execution))

        assert result.llm_verdict == "approved"
        assert len(result.llm_praise) == 1
        assert result.llm_praise[0]["description"] == "Excellent error handling"
        assert len(result.llm_suggestions) == 1
        assert "composing validator class" in result.llm_suggestions[0]["description"]
        # Verify prompt for suggestions & praise was sent
        sent_prompts = [
            msg.content
            for call in mock_chat_port.send.call_args_list
            for msg in call[0][0]
        ]
        assert any("architectural style" in prompt for prompt in sent_prompts)

