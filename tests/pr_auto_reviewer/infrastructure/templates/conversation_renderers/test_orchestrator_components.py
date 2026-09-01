from ._helpers import *


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
            attempts=[],
        )

        assert "Attempt #2 Returned No Surviving Findings" in content
        assert "**changes_requested**" in content
        assert "nothing found" in content

    def test_feedback_context_grounds_re_attempt_in_prior_results(self) -> None:
        content = FeedbackContextRenderer().render_content(
            round_number=2,
            escalation="re-derive a genuine verdict.",
            previous_verdict="approved",
            previous_explanation="no actionable findings",
            attempts=[{
                "attempt": 1,
                "reported": 3,
                "dropped": 3,
                "survived": 0,
                "verdict": "approved",
                "explanation": "3 reported, 3 dropped",
            }],
        )

        assert "**3** dropped during verification" in content
        assert "Attempt 1: **3** reported" in content

