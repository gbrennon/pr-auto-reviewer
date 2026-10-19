from ._helpers import *


class TestFeedbackRefusalGuard:
    """An inconclusive review re-runs; only a genuine verdict completes."""

    @staticmethod
    def _orchestrator(mock_command_bus, mock_tool_factory, **kwargs):
        return MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            **kwargs,
        )

    def test_refuted_findings_re_enter_the_feedback_loop(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        plan = ReviewPlan(
            phases=_plan(), methodology="sub-agent-multi-phase",
        )
        orchestrator = self._orchestrator(mock_command_bus, mock_tool_factory)
        refuted = _outcome(
            dropped_findings=3,
            verdict=ReviewVerdict.APPROVED,
            reason="The reported issues did not survive verification.",
            summary="The change is assessed as correct.",
        )
        orchestrator._run_phases = lambda *args, **kwargs: refuted

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
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED.value

    def test_genuinely_empty_result_also_enters_feedback_loop(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        plan = ReviewPlan(
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

        for attempt_number in (1, 2, 3):
            context = orchestrator._build_feedback_context(
                review, attempt_number, []
            )
            assert "unusual for a real code change" not in context
            assert "assume the diff contains" not in context

        final_context = orchestrator._build_feedback_context(review, 2, [])
        assert "valid outcome" in final_context

    def test_inconclusive_refutation_keeps_trying_then_raises_by_default(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        plan = ReviewPlan(
            phases=_plan(), methodology="sub-agent-multi-phase",
        )
        orchestrator = self._orchestrator(mock_command_bus, mock_tool_factory)
        initial_empty = _code_review(verdict=ReviewVerdict.APPROVED)
        calls: list[int] = []

        def _always_refuted(*args, **kwargs):
            calls.append(len(calls) + 1)
            return _outcome(
                dropped_findings=2,
                verdict=ReviewVerdict.APPROVED,
                reason="Findings refuted against source.",
            )

        orchestrator._run_phases = _always_refuted
        with _pytest.raises(ReviewVerdictError):
            orchestrator._run_feedback_loop(
                plan=plan,
                repo_path=Path("/tmp"),
                changed_files=["src/main.py"],
                model="test",
                previous_result=initial_empty,
                review_session="test-session",
                pr_identifier_service="owner/repo/1",
            )

        assert len(calls) == 1

    def test_inconclusive_refutation_raises_after_legacy_override_removal(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        plan = ReviewPlan(
            phases=_plan(), methodology="sub-agent-multi-phase",
        )
        orchestrator = self._orchestrator(
            mock_command_bus, mock_tool_factory,
        )
        initial_empty = _code_review(verdict=ReviewVerdict.APPROVED)
        calls: list[int] = []

        def _always_refuted(*args, **kwargs):
            calls.append(len(calls) + 1)
            return _outcome(
                dropped_findings=2,
                verdict=ReviewVerdict.APPROVED,
                reason="Findings refuted against source.",
            )

        orchestrator._run_phases = _always_refuted
        with _pytest.raises(ReviewVerdictError):
            orchestrator._run_feedback_loop(
                plan=plan,
                repo_path=Path("/tmp"),
                changed_files=["src/main.py"],
                model="test",
                previous_result=initial_empty,
                review_session="test-session",
                pr_identifier_service="owner/repo/1",
            )

        assert len(calls) == 1
