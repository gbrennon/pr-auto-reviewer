from ._helpers import *


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

