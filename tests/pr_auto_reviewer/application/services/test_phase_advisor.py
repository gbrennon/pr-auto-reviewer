"""Tests for PhaseAdvisor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pr_auto_reviewer.application.services.phase_advisor import PhaseAdvisor
from pr_auto_reviewer.domain.entities.engineer_agent import EngineerAgent
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.review_phase import ReviewPhase
from pr_auto_reviewer.domain.value_objects.sub_agent_grade import (
    SubAgentGrade,
)


def _phase() -> ReviewPhase:
    """A review phase with an engineer peer."""
    return ReviewPhase(
        phase_id="bug-hunt",
        phase_name="Bug Hunt",
        system_prompt="inspect the diff",
        role=EngineerAgent(),
    )


class TestPhaseAdvisor:
    """The advisor grades a finished phase against its assignment."""

    def test_assess_sends_grade_prompt_and_parses_directive(self) -> None:
        chat = MagicMock()
        chat.send.return_value = (
            '{"grade": "okok", "feedback": "stayed on task", '
            '"improved_prompt": ""}'
        )
        advisor = PhaseAdvisor(chat_port=chat)

        directive = advisor.assess(
            _phase(),
            "find bugs in the diff",
            PhaseResult(llm_verdict="approved", items=[]),
        )

        assert directive.grade is SubAgentGrade.OKOK
        assert directive.feedback == "stayed on task"
        assert directive.blocks_output is False
        assert len(chat.send.call_args_list) == 1
        messages = chat.send.call_args.args[0]
        assert any("impressive" in m.content for m in messages)

    def test_assess_parses_grade_from_fenced_json(self) -> None:
        chat = MagicMock()
        chat.send.return_value = (
            '```json\n{"grade": "don\'t do this!", "feedback": "off task", '
            '"improved_prompt": "re-explain the task"}\n```'
        )
        advisor = PhaseAdvisor(chat_port=chat)

        directive = advisor.assess(
            _phase(), "assignment", PhaseResult(),
        )

        assert directive.grade is SubAgentGrade.DONT_DO_THIS
        assert directive.feedback == "off task"
        assert directive.improved_prompt == "re-explain the task"
        assert directive.blocks_output is True

    def test_assess_unparseable_accepts_output(self) -> None:
        chat = MagicMock()
        chat.send.return_value = "the phase was great"
        advisor = PhaseAdvisor(chat_port=chat)

        directive = advisor.assess(
            _phase(), "assignment", PhaseResult(llm_verdict="approved"),
        )

        assert directive.grade is SubAgentGrade.OKOK
        assert directive.blocks_output is False

    def test_assess_chat_failure_accepts_output(self) -> None:
        chat = MagicMock()
        chat.send.side_effect = RuntimeError("ollama down")
        advisor = PhaseAdvisor(chat_port=chat)

        directive = advisor.assess(
            _phase(), "assignment", PhaseResult(),
        )

        assert directive.grade is SubAgentGrade.OKOK
        assert directive.blocks_output is False

    def test_assess_prompt_includes_peer_role_contract(self) -> None:
        chat = MagicMock()
        chat.send.return_value = '{"grade": "whatever"}'
        advisor = PhaseAdvisor(chat_port=chat)

        advisor.assess(
            _phase(), "find bugs", PhaseResult(),
        )

        messages = chat.send.call_args.args[0]
        user_content = messages[-1].content
        assert "engineer" in user_content
        assert "find bugs" in user_content
        assert "responsibility" in user_content.lower()

    @pytest.mark.parametrize(
        "key",
        ["grade", "verdict", "assessment"],
    )
    def test_assess_accepts_any_grade_key(self, key: str) -> None:
        chat = MagicMock()
        chat.send.return_value = (
            f'{{"{key}": "whatever", "feedback": "drifted"}}'
        )
        advisor = PhaseAdvisor(chat_port=chat)

        directive = advisor.assess(
            _phase(), "assignment", PhaseResult(),
        )

        assert directive.grade is SubAgentGrade.WHATEVER
        assert directive.feedback == "drifted"