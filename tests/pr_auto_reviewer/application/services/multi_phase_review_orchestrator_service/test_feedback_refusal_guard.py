from ._helpers import *


class TestFeedbackRefusalGuard:
    """A correct refutation publishes as-is; only genuine emptiness loops."""

    @staticmethod
    def _orchestrator(mock_command_bus, mock_tool_factory):
        return MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )

    def test_refuted_findings_publish_without_feedback_rounds(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        plan = SimpleNamespace(
            phases=_plan(), methodology="sub-agent-multi-phase",
        )
        orchestrator = self._orchestrator(mock_command_bus, mock_tool_factory)
        refuted = _outcome(
            dropped_findings=3,
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="The model reported 3 finding(s) that did not "
            "survive verification against the source code.",
        )
        orchestrator._run_phases = lambda *args, **kwargs: refuted

        def _forbidden_loop(*args, **kwargs):
            raise AssertionError(
                "feedback loop must not run after refutation"
            )

        orchestrator._run_feedback_loop = _forbidden_loop

        result = orchestrator._run_phases_full_retry(
            plan=plan,
            repo_path=Path("/tmp"),
            changed_files=["src/main.py"],
            model="test",
            review_session="test-session",
        )

        assert result.items == []
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED.value

    def test_genuinely_empty_result_still_enters_feedback_loop(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        plan = SimpleNamespace(
            phases=_plan(), methodology="sub-agent-multi-phase",
        )
        orchestrator = self._orchestrator(mock_command_bus, mock_tool_factory)
        genuinely_empty = _outcome(
            verdict=ReviewVerdict.APPROVED,
            reason="No issues found",
        )
        orchestrator._run_phases = lambda *args, **kwargs: genuinely_empty
        recovered = _code_review(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            items=[_make_review_item("src/main.py", "found later")],
        )
        orchestrator._run_feedback_loop = (
            lambda *args, **kwargs: recovered
        )

        result = orchestrator._run_phases_full_retry(
            plan=plan,
            repo_path=Path("/tmp"),
            changed_files=["src/main.py"],
            model="test",
            review_session="test-session",
        )

        assert len(result.items) == 1

    def test_feedback_context_contains_no_escalation_pressure(self) -> None:
        bus = InMemoryCommandBus()
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=bus, tool_factory=lambda *a, **k: MagicMock(),
        )
        review = _code_review(verdict=ReviewVerdict.APPROVED)

        for round_number in (1, 2, 3):
            context = orchestrator._build_feedback_context(
                review, round_number
            )
            assert "unusual for a real code change" not in context
            assert "assume the diff contains" not in context

        final_context = orchestrator._build_feedback_context(review, 2)
        assert "valid outcome" in final_context


    def test_feedback_loop_returns_early_when_round_drops_all_findings(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        plan = SimpleNamespace(
            phases=_plan(), methodology="sub-agent-multi-phase",
        )
        orchestrator = self._orchestrator(mock_command_bus, mock_tool_factory)
        initial_empty = _code_review(verdict=ReviewVerdict.APPROVED)

        calls = []
        def _mock_run_phases(*args, **kwargs):
            calls.append(len(calls) + 1)
            return _outcome(
                dropped_findings=2,
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                reason="Refuted findings",
            )

        orchestrator._run_phases = _mock_run_phases
        result = orchestrator._run_feedback_loop(
            plan=plan,
            repo_path=Path("/tmp"),
            changed_files=["src/main.py"],
            model="test",
            previous_result=initial_empty,
            review_session="test-session",
            pr_identifier_service="owner/repo/1",
        )

        assert len(calls) == 1
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED.value
