from ._helpers import *


class TestPhaseRetryForwardsBaseSha:
    """The PR merge-base reaches the exploration tool factory for each phase."""

    def test_factory_receives_base_sha(self) -> None:
        bus = InMemoryCommandBus()
        seen: dict[str, object] = {}

        def _factory(repo_path, changed_files, base_sha):
            seen["changed_files"] = list(changed_files)
            seen["base_sha"] = base_sha
            return MagicMock()

        def _phase_stub(command: RunAgentConversationCommand) -> PhaseResult:
            seen["phase_name"] = command.phase_name
            return PhaseResult(items=[], llm_verdict="approved")

        bus.register(RunAgentConversationCommand, _phase_stub)
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=bus, tool_factory=_factory,
        )
        result = orchestrator._run_phase_with_retry(
            phase_name="Bug Hunt — Diff",
            phase_prompt="EEP",
            repo_path=Path("."),
            changed_files=["src/a.py"],
            base_sha="d896687cafc093f113ade5444f02df98fcfc9042",
            review_session="test-session",
        )

        assert result.llm_verdict == "approved"
        assert seen["base_sha"] == "d896687cafc093f113ade5444f02df98fcfc9042"
        assert seen["changed_files"] == ["src/a.py"]
        assert seen["phase_name"] == "Bug Hunt — Diff"

