"""Behavioral tests for MarkdownConversationLogger."""

from types import SimpleNamespace
from typing import Any

from pr_auto_reviewer.infrastructure.conversation_logger import (
    MarkdownConversationLogger,
)


def _tool_call(name: str = "ls", arguments: dict[str, Any] | None = None) -> Any:
    return SimpleNamespace(tool_name=name, arguments=arguments or {})


def _tool_result(
    status: str = "ok",
    data: dict[str, Any] | None = None,
    error: str | None = None,
) -> Any:
    return SimpleNamespace(status=status, data=data, error=error)


def _message(role: str, content: str = "", **attrs: Any) -> Any:
    base = SimpleNamespace(role=role, content=content)
    return SimpleNamespace(**{**vars(base), **attrs})


class TestMarkdownConversationLogger:
    """Exercises MarkdownConversationLogger rendering and persistence."""

    def test_log_when_known_phase_then_uses_mapped_role(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Bug Hunt — Diff", "o/r", [], {"model": "m", "turns": 1}
        )

        text = path.read_text()
        assert "# Agent: engineer" in text
        assert "# Phase: Bug Hunt — Diff" in text
        assert "# PR: o/r" in text
        assert "| Verdict: unknown" in text

    def test_log_when_unknown_phase_then_uses_metadata_role(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Custom Review",
            "o/r",
            [],
            {"agent_role": "reviewer", "model": "m", "turns": 2, "verdict": "commented", "item_count": 3},
        )

        text = path.read_text()
        assert "# Agent: reviewer" in text
        assert "| Verdict: commented" in text
        assert "| Items: 3" in text

    def test_log_when_system_message_then_starts_turn(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Architecture Review",
            "o/r",
            [_message("system", "prompt text")],
            {"model": "m", "turns": 1},
        )

        assert "## Turn 1" in path.read_text()
        assert "### Sent — System Prompt (architect)" in path.read_text()

    def test_log_when_user_message_then_context_section(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Bug Hunt — Diff", "o/r", [_message("user", "context")], {"model": "m", "turns": 0}
        )

        text = path.read_text()
        assert "### Sent — Context" in text
        assert "context" in text

    def test_log_when_user_tool_result_then_tool_section(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)
        msg = _message(
            "user",
            "",
            tool_result=_tool_result(status="ok", data={"file": "a.py"}, error=None),
        )

        path = logger.log_conversation("Bug Hunt — Diff", "o/r", [msg], {"model": "m", "turns": 0})

        text = path.read_text()
        assert "### Received — Tool Result (`ok`)" in text
        assert '"file": "a.py"' in text

    def test_log_when_user_tool_result_error_then_error_line(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)
        msg = _message(
            "user",
            "",
            tool_result=_tool_result(status="error", data=None, error="boom"),
        )

        path = logger.log_conversation("Bug Hunt — Diff", "o/r", [msg], {"model": "m", "turns": 0})

        assert "**Error:** boom" in path.read_text()

    def test_log_when_assistant_tool_call_then_fn_section(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)
        msg = _message("assistant", "", tool_call=_tool_call("read_file", {"path": "a.py"}))

        path = logger.log_conversation("Bug Hunt — Diff", "o/r", [msg], {"model": "m", "turns": 0})

        text = path.read_text()
        assert "### Received — Tool Call (`read_file`)" in text
        assert '"path": "a.py"' in text

    def test_log_when_assistant_answer_then_answer_section(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Bug Hunt — Diff", "o/r", [_message("assistant", "answer")], {"model": "m", "turns": 0}
        )

        assert "### Received — Answer (engineer)" in path.read_text()

    def test_log_when_long_content_then_truncated(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Bug Hunt — Diff", "o/r", [_message("user", "x" * 5000)], {"model": "m", "turns": 0}
        )

        assert "(truncated)" in path.read_text()

    def test_log_when_long_system_content_then_truncated(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Bug Hunt — Diff", "o/r", [_message("system", "y" * 5000)], {"model": "m", "turns": 0}
        )

        assert "(truncated)" in path.read_text()

    def test_log_when_long_tool_data_then_truncated(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)
        msg = _message(
            "user", "", tool_result=_tool_result(status="ok", data={"big": "z" * 5000})
        )

        path = logger.log_conversation("Bug Hunt — Diff", "o/r", [msg], {"model": "m", "turns": 0})

        assert "(truncated)" in path.read_text()

    def test_log_when_long_answer_then_truncated(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Bug Hunt — Diff", "o/r", [_message("assistant", "a" * 5000)], {"model": "m", "turns": 0}
        )

        assert "(truncated)" in path.read_text()

    def test_log_default_dir_when_no_base_then_under_home_cache(self) -> None:
        logger = MarkdownConversationLogger()

        assert logger._base_dir.as_posix().endswith(".cache/pr-auto-reviewer/conversations")