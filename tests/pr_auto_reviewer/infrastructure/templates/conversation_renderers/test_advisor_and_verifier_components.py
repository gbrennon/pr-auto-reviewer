from ._helpers import *


class TestAdvisorAndVerifierComponents:
    """Grading and verification conversation components."""

    def test_turn_grade_user_message_carries_phase_and_peer_turn(self) -> None:
        message = AdvisorTurnGradeUserRenderer().render(
            phase_name="Bug Hunt — Diff", peer_content="peer output"
        )

        assert "Bug Hunt — Diff" in message.content
        assert "peer output" in message.content


    def test_turn_grade_user_message_carries_changed_files(self) -> None:
        message = AdvisorTurnGradeUserRenderer().render(
            phase_name="Bug Hunt — Diff",
            peer_content="peer output",
            changed_files=["Cargo.toml", "CHANGELOG.md"],
        )

        assert "Cargo.toml" in message.content
        assert "CHANGELOG.md" in message.content
    def test_verify_initial_user_message_carries_repo_path(self) -> None:
        message = VerifyInitialUserRenderer().render(repo_path="/repos/x")

        assert "/repos/x" in message.content
        assert "`results`" in message.content

    def test_suggestions_praise_message_renders_schema(self) -> None:
        message = SuggestionsPraiseMessageRenderer().render()

        assert "suggestions" in message.content
        assert "praise" in message.content
        assert "architectural style" in message.content
        assert "composition" in message.content

