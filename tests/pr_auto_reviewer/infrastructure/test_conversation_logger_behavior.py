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


_SESSION = "20260823_120000"
_PEER = "Bug Hunt — Diff"


class TestMarkdownConversationLogger:
    """Exercises MarkdownConversationLogger rendering and persistence."""

    def test_log_when_known_phase_then_uses_mapped_role(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r", [], {"model": "m", "turns": 1}, _SESSION,
        )

        text = path.read_text()
        assert "# engineer — " in text
        assert "# Phase: Bug Hunt — Diff" in text
        assert "# Review: 20260823_120000" in text

    def test_log_when_unknown_phase_then_uses_metadata_role(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Custom Phase", "o/r", [_message("assistant", "hi")],
            {"agent_role": "architect", "item_count": 3},
            _SESSION,
        )
        text = path.read_text()
        assert "# architect — " in text
        assert "| Items: 3" in text

    def test_log_when_system_message_then_starts_turn(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r",
            [_message("system", "sys prompt"), _message("assistant", "a")],
            {}, _SESSION,
        )

        assert "### Sent — System Prompt (engineer)" in path.read_text()

    def test_log_when_user_message_then_context_section(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r",
            [_message("user", "inspect the diff")], {}, _SESSION,
        )

        assert "### Sent — Context" in path.read_text()

    def test_log_when_user_tool_result_then_tool_section(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r",
            [_message("user", "", tool_result=_tool_result(data={"file": "a.py"}))],
            {}, _SESSION,
        )

        assert '"file": "a.py"' in path.read_text()

    def test_log_when_user_tool_result_error_then_error_line(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r",
            [_message("user", "", tool_result=_tool_result(error="boom"))],
            {}, _SESSION,
        )

        assert "**Error:** boom" in path.read_text()

    def test_log_when_assistant_tool_call_then_fn_section(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r",
            [_message("assistant", "", tool_call=_tool_call(arguments={"path": "a.py"}))],
            {}, _SESSION,
        )

        assert '"path": "a.py"' in path.read_text()

    def test_log_when_assistant_answer_then_answer_section(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r", [_message("assistant", "done")], {}, _SESSION,
        )

        assert "### Received — Answer (engineer)" in path.read_text()

    def test_log_when_long_content_then_truncated(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r",
            [_message("assistant", "x" * 6000)], {}, _SESSION,
        )

        assert "(truncated)" in path.read_text()

    def test_log_when_long_system_content_then_truncated(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r",
            [_message("system", "x" * 6000)], {}, _SESSION,
        )

        assert "(truncated)" in path.read_text()

    def test_log_when_long_tool_data_then_truncated(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r",
            [_message("user", "", tool_result=_tool_result(data={"pad": "x" * 5000}))],
            {}, _SESSION,
        )

        assert "(truncated)" in path.read_text()

    def test_log_when_long_answer_then_truncated(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r",
            [_message("assistant", "y" * 6000)], {}, _SESSION,
        )

        assert "(truncated)" in path.read_text()

    def test_log_default_dir_when_no_base_then_under_state_home(self) -> None:
        logger = MarkdownConversationLogger()

        assert logger._base_dir.as_posix().endswith(
            ".local/state/pr-auto-reviewer/conversations"
        )

    def test_log_writes_under_review_session_subdir(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)
        pr = "gbrennon/example#63"

        path = logger.log_conversation(
            _PEER, pr, [_message("assistant", "ok")], {}, _SESSION,
        )

        relative = path.relative_to(tmp_path)
        parts = list(relative.parts)
        assert parts[0] == "gbrennon_example_63"
        assert parts[1] == _SESSION
        assert relative.name == "01-bug-hunt-diff.md"

    def test_log_manager_planning_uses_planning_topic(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Bug Hunt — Diff", "o/r#1",
            [_message("assistant", "brief")],
            {"agent_role": "manager"}, _SESSION,
        )

        assert path.name == "00-planning.md"

    def test_log_advisor_grade_groups_with_observed_phase(
        self, tmp_path,
    ) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Bug Hunt — Diff", "o/r#1",
            [_message("assistant", "grade")],
            {"agent_role": "advisor"}, _SESSION,
        )

        assert path.name == "01-bug-hunt-diff.md"

    def test_log_advisor_grade_for_branch_phase_sorts_second(
        self, tmp_path,
    ) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Bug Hunt — Branch", "o/r#1",
            [_message("assistant", "grade")],
            {"agent_role": "advisor"}, _SESSION,
        )

        assert path.name == "02-bug-hunt-branch.md"

    def test_log_branch_phase_uses_second_ordinal(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Bug Hunt — Branch", "o/r#1",
            [_message("assistant", "findings")], {}, _SESSION,
        )

        assert path.name == "02-bug-hunt-branch.md"

    def test_log_architecture_phase_uses_third_ordinal(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Architecture Review", "o/r#1",
            [_message("assistant", "review")], {}, _SESSION,
        )

        assert path.name == "03-architecture-review.md"

    def test_log_verifier_uses_verifier_topic(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Verify Findings", "o/r#1",
            [_message("assistant", "verified")],
            {"agent_role": "verifier"}, _SESSION,
        )

        assert path.name == "05-verifier.md"

    def test_log_advisor_exchange_shows_grade_and_feedback(
        self, tmp_path,
    ) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r#1",
            [_message("assistant", "stayed on task")],
            {"agent_role": "advisor", "grade": "amazing",
             "feedback": "grounded progress"},
            _SESSION,
        )

        text = path.read_text()
        assert "Grade: amazing" in text
        assert "Feedback: grounded progress" in text
        assert "Verdict:" not in text
        assert "Items:" not in text

    def test_log_manager_exchange_omits_verdict_line(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            _PEER, "o/r#1",
            [_message("assistant", "brief")],
            {"agent_role": "manager"}, _SESSION,
        )

        text = path.read_text()
        assert "# manager — " in text
        assert "Verdict:" not in text

    def test_log_verifier_exchange_omits_verdict_line(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Verify Findings", "o/r#1",
            [_message("assistant", "verified")],
            {"agent_role": "verifier"}, _SESSION,
        )

        assert "Verdict:" not in path.read_text()

    def test_log_unknown_phase_sorts_last(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        path = logger.log_conversation(
            "Mystery Phase", "o/r#1",
            [_message("assistant", "hello")], {}, _SESSION,
        )

        assert path.name == "99-mystery_phase.md"