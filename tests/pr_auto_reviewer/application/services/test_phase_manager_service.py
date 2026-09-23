"""Tests for PhaseManagerService."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from pr_auto_reviewer.application.services.phase_manager_service import (
    PhaseManagerService,
)
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.entities.architect_agent import ArchitectAgent
from pr_auto_reviewer.domain.value_objects.review_phase import ReviewPhase


class TestPhaseManager:
    """The manager briefs the next phase with a focused task."""

    def test_brief_returns_manager_reply(self) -> None:
        chat = MagicMock()
        chat.send.return_value = "assign the architecture review to the architect"
        manager = PhaseManagerService(chat_port=chat)

        brief = manager.brief(
            ReviewPhase(
                phase_id="architect",
                phase_name="Architecture Review",
                system_prompt="AAP",
                role=ArchitectAgent(),
            ),
            "found bugs in src/a.py",

            review_session="test-session",
        )

        assert brief == "assign the architecture review to the architect"
        assert len(chat.send.call_args_list) == 1
        messages = chat.send.call_args.args[0]
        assert any("architect" in m.content for m in messages)
        assert any("src/a.py" in m.content for m in messages)

    def test_brief_empty_reply_returns_empty(self) -> None:
        chat = MagicMock()
        chat.send.return_value = "   "
        manager = PhaseManagerService(chat_port=chat)

        brief = manager.brief(
            ReviewPhase(phase_id="x", phase_name="X", system_prompt=""),
            "",

            review_session="test-session",
        )

        assert brief == ""

    def test_brief_chat_failure_returns_empty(self) -> None:
        chat = MagicMock()
        chat.send.side_effect = RuntimeError("parse error")
        manager = PhaseManagerService(chat_port=chat)

        brief = manager.brief(
            ReviewPhase(phase_id="x", phase_name="X", system_prompt=""),
            "findings",

            review_session="test-session",
        )

        assert brief == ""

    def test_brief_raises_llm_unavailable_error(self) -> None:
        chat = MagicMock()
        chat.send.side_effect = LlmUnavailableError("host unreachable")
        manager = PhaseManagerService(chat_port=chat)

        with pytest.raises(LlmUnavailableError, match="host unreachable"):
            manager.brief(
                ReviewPhase(phase_id="x", phase_name="X", system_prompt=""),
                "findings",
                review_session="test-session",
            )

    def test_brief_prompt_grounds_in_prior_findings(self) -> None:
        chat = MagicMock()
        chat.send.return_value = "task"
        manager = PhaseManagerService(chat_port=chat)

        manager.brief(
            ReviewPhase(
                phase_id="architect", phase_name="Architecture Review",
                system_prompt="AAP", role=ArchitectAgent(),
            ),
            "found bugs in src/a.py\nfound leak in src/b.py",

            review_session="test-session",
        )

        messages = chat.send.call_args.args[0]
        user_content = messages[-1].content
        assert "Architecture Review" in user_content
        assert "found bugs in src/a.py" in user_content
        assert "found leak in src/b.py" in user_content

    def test_brief_passes_untruncated_phase_instructions(self) -> None:
        chat = MagicMock()
        chat.send.return_value = "focused task"
        manager = PhaseManagerService(chat_port=chat)
        long_instructions = "Scope details " * 40 + "END_OF_INSTRUCTIONS"

        manager.brief(
            ReviewPhase(
                phase_id="diff_phase",
                phase_name="Bug Hunt — Diff",
                system_prompt=long_instructions,
                role=ArchitectAgent(),
            ),
            "",
            review_session="test-session",
        )

        messages = chat.send.call_args.args[0]
        user_content = messages[-1].content
        assert "END_OF_INSTRUCTIONS" in user_content