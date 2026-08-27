from ._helpers import *


class TestOrchestratorCommentedIsFailureMarker:
    """A ``commented`` LLM verdict is a pipeline failure, never an outcome."""

    @staticmethod
    def _build_review_orchestrator():

        bus = InMemoryCommandBus()
        parser = ReviewResponseParser()

        def _parse_turn(command: ParseReviewTurnCommand) -> TurnParseResult:
            return TurnParserService(parser).execute(command)

        bus.register(ParseReviewTurnCommand, _parse_turn)
        return MultiPhaseReviewOrchestratorService(
            command_bus=bus, tool_factory=lambda *a: None
        ), bus

    def test_legit_llm_verdict_survives_no_items_path(self) -> None:

        orchestrator, bus = self._build_review_orchestrator()

        def _run_phase(command: RunAgentConversationCommand) -> PhaseResult:
            return PhaseResult(
                items=[],
                llm_verdict="approved",
                llm_reason="No critical bugs identified.",
                llm_suggestions=[
                    {"file": "", "line": "", "description": "Add rate limiting."}
                ],
            )

        bus.register(RunAgentConversationCommand, _run_phase)
        plan = ReviewPlan(
            methodology="review",
            phases=(ReviewPhase(
                phase_id="advisor", phase_name="Advisor", system_prompt="x"
            ),),
        )
        review = orchestrator._run_phases_full_retry(
            plan=plan,
            repo_path=Path("."),
            changed_files=[],
            model="code-review:latest",
            review_session="test-session",
        )
        assert review.verdict == ReviewVerdict.APPROVED
        assert review.reason != ""
        assert review.summary != ""
        assert review.suggestions != []

    def test_commented_verdict_raises_instead_of_defaulting(self) -> None:

        orchestrator, bus = self._build_review_orchestrator()

        def _run_phase(command: RunAgentConversationCommand) -> PhaseResult:
            return PhaseResult(items=[], llm_verdict="commented")

        bus.register(RunAgentConversationCommand, _run_phase)
        plan = ReviewPlan(
            methodology="review",
            phases=(ReviewPhase(
                phase_id="advisor", phase_name="Advisor", system_prompt="x"
            ),),
        )
        with pytest.raises(ReviewVerdictError):
            orchestrator._run_phases_full_retry(
                plan=plan,
                repo_path=Path("."),
                changed_files=[],
                model="code-review:latest",
            review_session="test-session",
        )

    def test_rebuild_after_verification_explains_dropped_findings(self) -> None:

        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=InMemoryCommandBus(), tool_factory=lambda *a: None
        )
        previous = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="Found 1 critical (1 maintainability) and 2 major.",
            summary="Found 3 issue(s) (3 blocking across 3 file(s)).",
            items=[
                ReviewItem(id="id-1",
                    severity=ItemSeverity.CRITICAL,
                    category=IssueCategory.MAINTAINABILITY,
                    file_path="src/a.py",
                    description="Missing validation.",
                    current_code="def f():",
                    suggested_fix="Add validation.",
                ),
                ReviewItem(id="id-2",
                    severity=ItemSeverity.MAJOR,
                    category=IssueCategory.MAINTAINABILITY,
                    file_path="src/b.py",
                    description="No error handling.",
                    current_code="def g():",
                    suggested_fix="Add handling.",
                ),
            ],
            model_used="code-review:latest",
        )
        rebuilt = orchestrator._rebuild_after_verification(
            [], "code-review:latest", previous=previous
        )
        assert rebuilt.items == []
        assert "dropped" in rebuilt.reason
        assert "did not survive" in rebuilt.summary
        assert "2" in rebuilt.summary
        assert "3" not in rebuilt.reason

    def test_manager_briefs_first_phase_before_it_starts(self) -> None:
        """The opening phase runs on a manager-planned task, not a static prompt."""

        manager = MagicMock()
        manager.brief.return_value = "Focus exclusively on install scripts."
        bus = InMemoryCommandBus()
        seen_prompts: list[str] = []

        def _phase_stub(command: RunAgentConversationCommand) -> PhaseResult:
            seen_prompts.append(command.system_prompt)
            return PhaseResult(items=[], llm_verdict="approved")

        bus.register(RunAgentConversationCommand, _phase_stub)
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=bus, tool_factory=lambda *a: None, manager=manager,
        )
        plan = ReviewPlan(
            methodology="review",
            phases=(ReviewPhase(
                phase_id="engineer", phase_name="Bug Hunt — Diff",
                system_prompt="EEP",
            ),),
        )
        orchestrator._run_phases(
            plan=plan, repo_path=Path("."), changed_files=[], model="m",
        )

        assert manager.brief.call_count == 1
        briefed_phase = manager.brief.call_args[0][0]
        assert briefed_phase.phase_id == "engineer"
        assert seen_prompts
        assert "Focus exclusively on install scripts." in seen_prompts[0]

    def test_advisor_backed_non_blocking_grade_accepts_output(self) -> None:
        """A wired advisor with a non-blocking grade accepts the phase unchanged.

        Regression: the grade cap moved into ``PhaseAdvisorService.assess``; the
        orchestrator must not reference its own (removed) copy.
        """
        advisor = MagicMock()
        advisor.assess.return_value = AdvisorDirective(
            grade=SubAgentGrade.OKOK,
        )
        bus = InMemoryCommandBus()

        def _phase_stub(command: RunAgentConversationCommand) -> PhaseResult:
            return PhaseResult(items=[], llm_verdict="approved")

        bus.register(RunAgentConversationCommand, _phase_stub)
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=bus, tool_factory=lambda *a: None, advisor=advisor,
        )
        plan = ReviewPlan(
            methodology="review",
            phases=(ReviewPhase(
                phase_id="engineer", phase_name="Bug Hunt — Diff",
                system_prompt="EEP",
            ),),
        )

        review = orchestrator._run_phases(
            plan=plan, repo_path=Path("."), changed_files=[], model="m",
        ).review

        assert advisor.assess.call_count == 1
        assert review.verdict is ReviewVerdict.APPROVED
        assert review.model_used == "m"

    def test_advisor_blocked_grade_restarts_phase_once(self) -> None:
        """A blocking F grade discards output and re-runs the phase."""
        advisor = MagicMock()
        advisor.assess.return_value = AdvisorDirective(
            grade=SubAgentGrade.DONT_DO_THIS, feedback="drifted off task",
        )
        bus = InMemoryCommandBus()
        runs: list[str] = []

        def _phase_stub(command: RunAgentConversationCommand) -> PhaseResult:
            runs.append(command.system_prompt)
            return PhaseResult(items=[], llm_verdict="approved")

        bus.register(RunAgentConversationCommand, _phase_stub)
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=bus, tool_factory=lambda *a: None, advisor=advisor,
        )
        plan = ReviewPlan(
            methodology="review",
            phases=(ReviewPhase(
                phase_id="engineer", phase_name="Bug Hunt — Diff",
                system_prompt="EEP",
            ),),
        )

        orchestrator._run_phases(
            plan=plan, repo_path=Path("."), changed_files=[], model="m",
        )

        assert len(runs) == 2

    def test_blocked_correction_strips_invented_identifiers(self) -> None:
        """An F-feedback citing an unobserved class cannot reach the peer."""
        advisor = MagicMock()
        advisor.assess.return_value = AdvisorDirective(
            grade=SubAgentGrade.DONT_DO_THIS,
            feedback=(
                "AppInbound is wrong; keep the PortLevel ordering "
                "documented in the phase output."
            ),
        )
        bus = InMemoryCommandBus()
        runs: list[str] = []
        observed_item = _make_review_item(
            "src/ports/_port_level.py",
            "PortLevel depth ordering is correct",
        )

        def _phase_stub(command: RunAgentConversationCommand) -> PhaseResult:
            runs.append(command.system_prompt)
            return PhaseResult(
                items=[observed_item], llm_verdict="approved",
            )

        def _aggregate_stub(command: AggregateReviewFindingsCommand):
            assert command.items, "expected the observed item to aggregate"
            return _code_review(items=list(command.items))

        bus.register(RunAgentConversationCommand, _phase_stub)
        bus.register(AggregateReviewFindingsCommand, _aggregate_stub)
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=bus, tool_factory=lambda *a: None, advisor=advisor,
        )
        plan = ReviewPlan(
            methodology="review",
            phases=(ReviewPhase(
                phase_id="engineer", phase_name="Bug Hunt — Diff",
                system_prompt="EEP",
            ),),
        )

        orchestrator._run_phases(
            plan=plan, repo_path=Path("."), changed_files=[], model="m",
        )

        assert len(runs) == 2
        assert "AppInbound" not in runs[1]
        assert "PortLevel" in runs[1]

