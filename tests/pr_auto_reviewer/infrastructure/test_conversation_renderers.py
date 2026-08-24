"""Behavioral tests for the conversation template renderer components."""

from __future__ import annotations

import jinja2
import pytest

from pr_auto_reviewer.infrastructure.templates.conversation_renderers import (
    AdvisorBlockMessageRenderer,
    AdvisorTurnGradeUserRenderer,
    EmptyResponseMessageRenderer,
    ExploreBeforeVerdictMessageRenderer,
    FeedbackContextRenderer,
    ForceVerdictMessageRenderer,
    InitialUserMessageRenderer,
    PhasePromptRenderer,
    RepeatedToolCallMessageRenderer,
    VerifyInitialUserRenderer,
)


class TestReviewPhaseComponents:
    """Review-phase loop messages render their contracts."""

    def test_initial_user_message_carries_files_repo_and_json_contract(
        self,
    ) -> None:
        message = InitialUserMessageRenderer().render(
            file_listing="src/a.py\n  - src/b.py",
            repo_path="/repos/owner_repo_42",
        )

        assert message.role == "user"
        assert "Changed files for this review:" in message.content
        assert "  - src/a.py\n  - src/b.py" in message.content
        assert "/repos/owner_repo_42" in message.content
        assert '"verdict"' in message.content
        assert '"action"' in message.content

    def test_empty_response_message_requests_verdict_json(self) -> None:
        message = EmptyResponseMessageRenderer().render()

        assert "previous response was empty" in message.content
        assert '"verdict"' in message.content

    def test_repeated_tool_call_message_refuses_repetition(self) -> None:
        message = RepeatedToolCallMessageRenderer().render()

        assert "You already ran that exact tool call" in message.content

    def test_force_verdict_message_demands_conclusion(self) -> None:
        message = ForceVerdictMessageRenderer().render()

        assert "You have explored enough. Conclude now" in message.content

    def test_explore_before_verdict_message_demands_exploration(self) -> None:
        message = ExploreBeforeVerdictMessageRenderer().render()

        assert "MUST use the exploration tools" in message.content

    def test_advisor_block_message_includes_feedback(self) -> None:
        message = AdvisorBlockMessageRenderer().render(feedback="stop looping")

        assert message.role == "user"
        assert "ADVISOR" in message.content
        assert "stop looping" in message.content


class TestAdvisorAndVerifierComponents:
    """Grading and verification conversation components."""

    def test_turn_grade_user_message_carries_phase_and_peer_turn(self) -> None:
        message = AdvisorTurnGradeUserRenderer().render(
            phase_name="Bug Hunt — Diff", peer_content="peer output"
        )

        assert "Bug Hunt — Diff" in message.content
        assert "peer output" in message.content

    def test_verify_initial_user_message_carries_repo_path(self) -> None:
        message = VerifyInitialUserRenderer().render(repo_path="/repos/x")

        assert "/repos/x" in message.content
        assert "`results`" in message.content


class TestOrchestratorComponents:
    """Orchestrator-level prompt assembly components."""

    def test_phase_prompt_layers_sections_in_order(self) -> None:
        content = PhasePromptRenderer().render_content(
            feedback="FEEDBACK",
            assignment="ASSIGNMENT",
            role_brief="ROLE_BRIEF",
            methodology="METHODOLOGY",
            system_prompt="SYSTEM_PROMPT",
        )

        assert content.index("FEEDBACK") < content.index("ASSIGNMENT")
        assert content.index("ASSIGNMENT") < content.index("ROLE_BRIEF")
        assert content.index("ROLE_BRIEF") < content.index("METHODOLOGY")
        assert content.index("METHODOLOGY") < content.index("SYSTEM_PROMPT")

    def test_phase_prompt_omits_absent_sections(self) -> None:
        content = PhasePromptRenderer().render_content(
            feedback="",
            assignment="",
            role_brief="",
            methodology="METHODOLOGY",
            system_prompt="SYSTEM_PROMPT",
        )

        assert content == "METHODOLOGY\n\nSYSTEM_PROMPT"

    def test_feedback_context_reports_verdict_and_explanation(self) -> None:
        content = FeedbackContextRenderer().render_content(
            round_number=2,
            escalation="dig deeper.",
            previous_verdict="changes_requested",
            previous_explanation="nothing found",
        )

        assert "Attempt #2 Returned No Findings" in content
        assert "**changes_requested**" in content
        assert "nothing found" in content


class TestTemplateWiringContract:
    """Templates fail fast on incomplete wiring via StrictUndefined."""

    def test_missing_context_variable_raises(self) -> None:
        with pytest.raises(jinja2.exceptions.UndefinedError):
            InitialUserMessageRenderer().render(file_listing="only-files.j2")
