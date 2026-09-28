from ._helpers import *


class _BudgetTrackingChatPort:
    def __init__(self) -> None:
        self.calls_started = 0

    def send(self, messages) -> str:
        self.calls_started += 1
        return ""

    def reset_budget(self) -> None:
        self.calls_started = 0


class TestOrchestratorResetsBudgetPerReview:
    """Each review must start with a fresh LLM call budget."""

    def _command(
        self, plan: ReviewPlan
    ) -> RunMultiPhaseReviewCommand:
        return RunMultiPhaseReviewCommand(
            plan=plan,
            repo_path=Path("/tmp"),
            changed_files=["src/main.py"],
            model="test",
            review_session="test-session",
        )

    def test_execute_resets_chat_client_budget_before_running_phases(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        chat_port = _BudgetTrackingChatPort()
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            chat_client=chat_port,
        )
        orchestrator._run_phases = lambda *a, **k: _outcome(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            items=[_make_review_item("src/main.py", "found")],
        )
        plan = ReviewPlan(
            phases=_plan(), methodology="sub-agent-multi-phase"
        )
        chat_port.calls_started = 300

        orchestrator.execute(self._command(plan))

        assert chat_port.calls_started == 0
