"""Integration tests for transcript lifecycle across a full review run.

These exercise MarkdownConversationLogger against a real (temporary)
directory tree and enforce the reading-order contract: one transcript
file per phase topic per review session, ordinals increasing in review
order, repeated conversations appending to the same file.
"""

from types import SimpleNamespace
from typing import Any

from pr_auto_reviewer.infrastructure.conversation_logger import (
    MarkdownConversationLogger,
)

_SESSION = "20260824_014537"
_PR = "gbrennon/pr-auto-reviewer#147"

_EXPECTED_READING_ORDER = [
    "00-planning.md",
    "01-bug-hunt-diff.md",
    "02-bug-hunt-branch.md",
    "03-architecture-review.md",
    "05-verifier.md",
]


class TestMarkdownConversationLoggerReviewRun:
    """Exercises transcript file lifecycle over a simulated review."""

    def _message(self, role: str, content: str = "", **attrs: Any) -> Any:
        base = SimpleNamespace(role=role, content=content)
        return SimpleNamespace(**{**vars(base), **attrs})

    def _log_full_review(self, logger: MarkdownConversationLogger) -> None:
        logger.log_conversation(
            "Bug Hunt — Diff", _PR,
            [self._message("assistant", "brief for diff hunt")],
            {"agent_role": "manager"}, _SESSION,
        )
        logger.log_conversation(
            "Bug Hunt — Diff", _PR,
            [
                self._message("system", "hunt the diff"),
                self._message("assistant", "first attempt answer"),
            ],
            {}, _SESSION,
        )
        logger.log_conversation(
            "Bug Hunt — Diff", _PR,
            [self._message("assistant", "grade: F")],
            {"agent_role": "advisor"}, _SESSION,
        )
        logger.log_conversation(
            "Bug Hunt — Diff", _PR,
            [self._message("assistant", "re-planned prompt")],
            {"agent_role": "manager"}, _SESSION,
        )
        logger.log_conversation(
            "Bug Hunt — Diff", _PR,
            [
                self._message("system", "re-planned hunt"),
                self._message("assistant", "second attempt answer"),
            ],
            {}, _SESSION,
        )
        logger.log_conversation(
            "Bug Hunt — Branch", _PR,
            [
                self._message("system", "hunt the branch"),
                self._message("assistant", "branch findings"),
            ],
            {}, _SESSION,
        )
        logger.log_conversation(
            "Bug Hunt — Branch", _PR,
            [self._message("assistant", "grade: B")],
            {"agent_role": "advisor"}, _SESSION,
        )
        logger.log_conversation(
            "Architecture Review", _PR,
            [
                self._message("system", "review architecture"),
                self._message("assistant", "architecture findings"),
            ],
            {}, _SESSION,
        )
        logger.log_conversation(
            "Verify Findings", _PR,
            [self._message("assistant", "verified")],
            {"agent_role": "verifier"}, _SESSION,
        )

    def test_full_review_creates_one_file_per_phase_in_counter_order(
        self, tmp_path,
    ) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        self._log_full_review(logger)

        session_dir = tmp_path / "gbrennon_pr-auto-reviewer_147" / _SESSION
        names = sorted(path.name for path in session_dir.glob("*.md"))
        assert names == _EXPECTED_READING_ORDER

    def test_restarted_phase_appends_turns_to_same_file(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        self._log_full_review(logger)

        diff_transcript = (
            tmp_path / "gbrennon_pr-auto-reviewer_147" / _SESSION
            / "01-bug-hunt-diff.md"
        )
        text = diff_transcript.read_text()
        assert "first attempt answer" in text
        assert "second attempt answer" in text
        assert "## Turn 1" in text
        assert "## Turn 2" in text

    def test_advisor_grades_share_the_phase_file(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        self._log_full_review(logger)

        diff_text = (
            tmp_path / "gbrennon_pr-auto-reviewer_147" / _SESSION
            / "01-bug-hunt-diff.md"
        ).read_text()
        branch_text = (
            tmp_path / "gbrennon_pr-auto-reviewer_147" / _SESSION
            / "02-bug-hunt-branch.md"
        ).read_text()
        assert "grade: F" in diff_text
        assert "grade: B" in branch_text

    def test_conversation_headers_carry_the_acting_role(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)

        logger.log_conversation(
            "Bug Hunt — Diff", _PR,
            [self._message("assistant", "brief")],
            {"agent_role": "manager"}, _SESSION,
        )
        logger.log_conversation(
            "Bug Hunt — Diff", _PR,
            [self._message("assistant", "hunt")],
            {}, _SESSION,
        )
        logger.log_conversation(
            "Bug Hunt — Diff", _PR,
            [self._message("assistant", "grade: B")],
            {"agent_role": "advisor"}, _SESSION,
        )

        session_dir = tmp_path / "gbrennon_pr-auto-reviewer_147" / _SESSION
        planning_text = (session_dir / "00-planning.md").read_text()
        diff_text = (session_dir / "01-bug-hunt-diff.md").read_text()
        assert "# manager — " in planning_text
        assert "# engineer — " in diff_text
        assert "# advisor — " in diff_text
        assert "# manager" not in diff_text
        assert "# engineer" not in planning_text

    def test_separate_review_sessions_get_isolated_files(self, tmp_path) -> None:
        logger = MarkdownConversationLogger(tmp_path)
        first_session = "20260824_010000"
        second_session = "20260824_020000"

        for session in (first_session, second_session):
            logger.log_conversation(
                "Bug Hunt — Diff", _PR,
                [self._message("assistant", f"run {session}")],
                {}, session,
            )

        pr_dir = tmp_path / "gbrennon_pr-auto-reviewer_147"
        for session in (first_session, second_session):
            session_files = list((pr_dir / session).glob("*.md"))
            assert [path.name for path in session_files] == ["01-bug-hunt-diff.md"]
