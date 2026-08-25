"""Tests for PhaseAdvisor."""

from __future__ import annotations

from unittest.mock import MagicMock

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

            review_session="test-session",
        )

        assert directive.grade is SubAgentGrade.OKOK
        assert directive.feedback == "stayed on task"
        assert directive.blocks_output is False
        assert len(chat.send.call_args_list) == 1
        messages = chat.send.call_args.args[0]
        assert any("impressive" in m.content for m in messages)

    def test_assess_publishes_exchange_with_grade_metadata(self) -> None:
        chat = MagicMock()
        chat.send.return_value = (
            '{"grade": "amazing", "feedback": "grounded progress"}'
        )
        bus = MagicMock()
        advisor = PhaseAdvisor(chat_port=chat, command_bus=bus)

        advisor.assess(
            _phase(), "assignment",
            PhaseResult(
                llm_verdict="approved", items=[], run_snippet_calls=1,
            ),
            review_session="test-session",
        )

        event = bus.dispatch.call_args.args[0]
        assert event.role == "advisor"
        assert event.metadata["grade"] == "amazing"
        assert event.metadata["feedback"] == "grounded progress"

    def test_observe_publishes_exchange_with_grade_metadata(self) -> None:
        chat = MagicMock()
        chat.send.return_value = '{"grade": "whatever", "feedback": "drifted"}'
        bus = MagicMock()
        advisor = PhaseAdvisor(chat_port=chat, command_bus=bus)

        advisor.observe(
            peer_content='{"action": "run_git", "args": ""}',
            phase_name="Bug Hunt — Diff",
            review_session="test-session",
        )

        event = bus.dispatch.call_args.args[0]
        assert event.role == "advisor"
        assert event.metadata["grade"] == "whatever"
        assert event.metadata["feedback"] == "drifted"

    def test_assess_parses_grade_from_fenced_json(self) -> None:
        chat = MagicMock()
        chat.send.return_value = (
            '```json\n{"grade": "don\'t do this!", "feedback": "off task", '
            '"improved_prompt": "re-explain the task"}\n```'
        )
        advisor = PhaseAdvisor(chat_port=chat)

        directive = advisor.assess(
            _phase(), "assignment", PhaseResult(),

            review_session="test-session",
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

            review_session="test-session",
        )

        assert directive.grade is SubAgentGrade.OKOK
        assert directive.blocks_output is False

    def test_assess_chat_failure_accepts_output(self) -> None:
        chat = MagicMock()
        chat.send.side_effect = RuntimeError("ollama down")
        advisor = PhaseAdvisor(chat_port=chat)

        directive = advisor.assess(
            _phase(), "assignment", PhaseResult(),

            review_session="test-session",
        )

        assert directive.grade is SubAgentGrade.OKOK
        assert directive.blocks_output is False

    def test_assess_prompt_includes_peer_role_contract(self) -> None:
        chat = MagicMock()
        chat.send.return_value = '{"grade": "whatever"}'
        advisor = PhaseAdvisor(chat_port=chat)

        advisor.assess(
            _phase(), "find bugs", PhaseResult(),

            review_session="test-session",
        )

        messages = chat.send.call_args.args[0]
        user_content = messages[-1].content
        assert "engineer" in user_content
        assert "find bugs" in user_content
        assert "responsibility" in user_content.lower()

    def test_assess_reads_grade_from_the_documented_key(self) -> None:
        chat = MagicMock()
        chat.send.return_value = (
            '{"grade": "whatever", "feedback": "drifted"}'
        )
        advisor = PhaseAdvisor(chat_port=chat)

        directive = advisor.assess(
            _phase(), "assignment", PhaseResult(),
            review_session="test-session",
        )

        assert directive.grade is SubAgentGrade.WHATEVER
        assert directive.feedback == "drifted"

    def test_assess_never_treats_a_verdict_key_as_a_grade(self) -> None:
        chat = MagicMock()
        chat.send.return_value = (
            '{"verdict": "changes_requested", "reason": "found bugs"}'
        )
        advisor = PhaseAdvisor(chat_port=chat)

        directive = advisor.assess(
            _phase(), "assignment", PhaseResult(),
            review_session="test-session",
        )

        assert directive.grade is SubAgentGrade.OKOK
        assert directive.feedback == ""
        assert directive.blocks_output is False

    def test_observe_never_treats_a_verdict_key_as_a_grade(self) -> None:
        chat = MagicMock()
        chat.send.return_value = '{"verdict": "approved"}'
        advisor = PhaseAdvisor(chat_port=chat)

        directive = advisor.observe(
            peer_content="turn", phase_name="Bug Hunt — Diff",
            review_session="test-session",
        )

        assert directive.grade is SubAgentGrade.OKOK
        assert directive.blocks_output is False

    def test_grade_prompt_carries_tool_evidence_counts(self) -> None:
        chat = MagicMock()
        chat.send.return_value = '{"grade": "okok"}'
        advisor = PhaseAdvisor(chat_port=chat)
        result = PhaseResult(
            llm_verdict="approved",
            turn_count=6,
            read_file_calls=3,
            run_snippet_calls=1,
        )

        advisor.assess(
            _phase(), "find bugs", result,
            review_session="test-session",
        )

        sent = chat.send.call_args.args[0]
        evidence_lines = [
            m.content for m in sent if "Tool evidence:" in m.content
        ]
        assert len(evidence_lines) == 1
        assert "turns: 6" in evidence_lines[0]
        assert "read_file: 3" in evidence_lines[0]
        assert "run_snippet: 1" in evidence_lines[0]

    def test_impressive_with_zero_snippets_is_capped_to_okok(self) -> None:
        chat = MagicMock()
        chat.send.return_value = '{"grade": "impressive"}'
        bus = MagicMock()
        advisor = PhaseAdvisor(chat_port=chat, command_bus=bus)
        result = PhaseResult(
            llm_verdict="approved", turn_count=4, run_snippet_calls=0,
        )

        directive = advisor.assess(
            _phase(), "find bugs", result,
            review_session="test-session",
        )

        assert directive.grade is SubAgentGrade.OKOK
        event = bus.dispatch.call_args.args[0]
        assert event.metadata["grade"] == "okok"

    def test_impressive_survives_when_a_snippet_ran(self) -> None:
        chat = MagicMock()
        chat.send.return_value = '{"grade": "impressive"}'
        advisor = PhaseAdvisor(chat_port=chat)
        result = PhaseResult(
            llm_verdict="approved", turn_count=6, run_snippet_calls=2,
        )

        directive = advisor.assess(
            _phase(), "find bugs", result,
            review_session="test-session",
        )

        assert directive.grade is SubAgentGrade.IMPRESSIVE

    def test_non_top_grades_pass_through_uncapped(self) -> None:
        chat = MagicMock()
        chat.send.return_value = '{"grade": "whatever"}'
        advisor = PhaseAdvisor(chat_port=chat)
        result = PhaseResult(llm_verdict="approved", run_snippet_calls=0)

        directive = advisor.assess(
            _phase(), "find bugs", result,
            review_session="test-session",
        )

        assert directive.grade is SubAgentGrade.WHATEVER