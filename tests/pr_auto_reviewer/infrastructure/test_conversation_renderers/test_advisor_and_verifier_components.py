from ._helpers import *


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

