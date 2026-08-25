from ._helpers import *


class TestMultiPhaseReviewOrchestrator:
    """Tests for the MultiPhaseReviewOrchestratorService."""

    def test_execute_full_retry(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Full execution returns the review produced by the phase run."""
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            max_retries=2,
        )
        plan = SimpleNamespace(phases=_plan(), methodology="sub-agent-multi-phase")
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(), pr_identifier_service="", review_session="", base_sha="": _outcome(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            items=[_make_review_item("src/main.py", "found")],
        )
        result = orchestrator.execute(
            type("Cmd", (), {"existing_item_ids": frozenset(), "review_session": "test-session",
                "base_sha": "",
                "plan": plan,
                "repo_path": Path("/tmp"),
                "changed_files": ["src/main.py"],
                "model": "test",
            })()
        )
        assert result is not None
        assert len(result.items) == 1

    def test_execute_with_llm_unavailable(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test execution when LLM is unavailable."""
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            max_retries=1,
        )
        plan = SimpleNamespace(phases=_plan(), methodology="sub-agent-multi-phase")

        def failing_run_phases(*args, **kwargs):
            raise MaxTurnsExceededError("Phase exceeded max turns (attempt 1)")

        orchestrator._run_phases = failing_run_phases
        # After max retries with no findings, refusing a default outcome is
        # mandatory: no silent COMMENTED fallback may be published.

        with _pytest.raises(ReviewVerdictError):
            orchestrator.execute(
                type("Cmd", (), {"existing_item_ids": frozenset(), "review_session": "test-session",
                    "base_sha": "",
                    "plan": plan,
                    "repo_path": Path("/tmp"),
                    "changed_files": ["src/main.py"],
                    "model": "test",
                })()
            )

    def test__run_phases_full_retry_no_items(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _run_phases_full_retry when no items are found."""
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            max_retries=3,
        )

        plan = _plan()

        # Make _run_phases return a result with no items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(), pr_identifier_service="", review_session="", base_sha="": _outcome(
            verdict=ReviewVerdict.APPROVED,
            reason="No issues found",
            summary="No issues found",
        )
        orchestrator._run_feedback_loop = lambda plan, repo_path, changed_files, model, previous_result, existing_item_ids=frozenset(), pr_identifier_service="", review_session="", base_sha="": _outcome(
            verdict=ReviewVerdict.APPROVED,
            reason="Recovered after feedback",
            summary="Issues resolved",
            items=[_make_review_item("src/main.py", "kept")],
        ).review

        result = orchestrator._run_phases_full_retry(
            plan=plan,
            repo_path=Path("/tmp"),
            changed_files=["src/main.py"],
            model="test",
            review_session="test-session",
        )

        assert result.verdict == ReviewVerdict.APPROVED.value
        assert len(result.items) == 1


    def test__run_phases_full_retry_with_items(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _run_phases_full_retry when items are found."""
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            max_retries=1,
        )

        plan = _plan()

        # Make _run_phases return a result with items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(), pr_identifier_service="", review_session="", base_sha="": _outcome(
            verdict=ReviewVerdict.APPROVED,
            reason="LGTM",
            summary="Looks good",
            items=[_make_review_item("src/main.py", "fix something")],
        )

        result = orchestrator._run_phases_full_retry(
            plan=plan,
            repo_path=Path("/tmp"),
            changed_files=["src/main.py"],
            model="test",
            review_session="test-session",
        )

        assert result.verdict == ReviewVerdict.APPROVED.value
        assert len(result.items) == 1

    def test__run_feedback_loop(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _run_feedback_loop logic."""
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            max_feedback_rounds=2,
        )

        plan = _plan()

        # Second round returns items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(), pr_identifier_service="", review_session="", base_sha="": _outcome(
            verdict=ReviewVerdict.APPROVED,
            reason="Fixed",
            summary="Issues fixed",
            items=[_make_review_item("src/main.py", "fixed")],
        )

        result = orchestrator._run_feedback_loop(
            plan=plan,
            repo_path=Path("/tmp"),
            changed_files=["src/main.py"],
            model="test",
            review_session="test-session",
            pr_identifier_service="o/r#1",
            previous_result=_code_review(verdict=ReviewVerdict.CHANGES_REQUESTED),
        )

        assert result.verdict == ReviewVerdict.APPROVED.value
        assert len(result.items) == 1

    def test__build_feedback_context(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _build_feedback_context."""
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )

        result = _code_review(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="No issues",
            summary="No issues found",
        )

        context = orchestrator._build_feedback_context(result, 1)
        assert "Attempt #1" in context
        assert "No issues found" in context

    def test_feedback_prepended_to_every_phase_not_just_first(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Escalation reaches ALL phases in a feedback round, so logs differ."""
        plan = ReviewPlan(
            phases=(
                ReviewPhase(
                    phase_id="engineer", phase_name="Engineer Review",
                    system_prompt="EEP",
                ),
                ReviewPhase(
                    phase_id="architect", phase_name="Architecture Review",
                    system_prompt="AAP",
                ),
            ),
            methodology="MM",
        )
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )
        phase_result = _phase_result(verdict="approved")
        mock_command_bus.dispatch.side_effect = [
            phase_result, MagicMock(), phase_result, MagicMock(),
            phase_result, MagicMock(), phase_result, MagicMock(),
        ]
        feedback = orchestrator._build_feedback_context(
            _code_review(verdict=ReviewVerdict.CHANGES_REQUESTED), 1
        )

        orchestrator._run_phases(
            plan, Path("/tmp"), ["src/main.py"], "test",
            initial_feedback=feedback,
        )

        prompts = [
            call[0][0].system_prompt
            for call in mock_command_bus.dispatch.call_args_list
            if isinstance(call[0][0], RunAgentConversationCommand)
        ]
        assert len(prompts) == 2  # one conversation command per phase
        phase_prompts = [p for p in prompts if "EEP" in p or "AAP" in p]
        assert len(phase_prompts) == 2
        assert all(feedback in p for p in phase_prompts)

    def test_role_brief_and_manager_brief_reach_phase_prompts(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Phase role and plan manager brief are composed into phase prompts."""
        plan = ReviewPlan(
            phases=(
                ReviewPhase(
                    phase_id="engineer", phase_name="Engineer Review",
                    system_prompt="EEP", role=EngineerAgent(),
                ),
                ReviewPhase(
                    phase_id="architect", phase_name="Architecture Review",
                    system_prompt="AAP",
                ),
            ),
            methodology="MM",
            manager_brief="MANAGER BRIEF TEXT",
        )
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )
        phase_result = _phase_result(verdict="approved")
        mock_command_bus.dispatch.side_effect = [
            phase_result, MagicMock(), phase_result, MagicMock(),
        ]

        orchestrator._run_phases(
            plan, Path("/tmp"), ["src/main.py"], "test",
        )

        prompts = [
            call[0][0].system_prompt
            for call in mock_command_bus.dispatch.call_args_list
            if isinstance(call[0][0], RunAgentConversationCommand)
        ]
        assert len(prompts) == 2
        phase_prompts = [p for p in prompts if "EEP" in p or "AAP" in p]
        assert phase_prompts[0].startswith("MANAGER BRIEF TEXT")
        assert "Your role: engineer" in phase_prompts[0]
        assert "Your role: engineer" not in phase_prompts[1]

    def test__run_phases_with_feedback(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _run_phases with initial_feedback."""
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )

        plan = _plan()

        # First run returns no items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(), pr_identifier_service="", review_session="", base_sha="": _outcome(
            verdict=ReviewVerdict.APPROVED,
            reason="No issues",
            summary="No issues",
        )

        # Second run with feedback returns items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(), pr_identifier_service="", review_session="", base_sha="": _outcome(
            verdict=ReviewVerdict.APPROVED,
            reason="Fixed",
            summary="Issues fixed",
            items=[_make_review_item("src/main.py", "fixed")],
        )

        result = orchestrator._run_phases_full_retry(
            plan=plan,
            repo_path=Path("/tmp"),
            changed_files=["src/main.py"],
            model="test",
            review_session="test-session",
        )

        assert result.verdict == ReviewVerdict.APPROVED.value

    def test__rebuild_after_verification(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _rebuild_after_verification."""
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )

        verified_items = [_make_review_item("src/main.py", "kept item")]
        previous = _code_review(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            items=[_make_review_item("src/main.py", "dropped item")],
        )

        result = orchestrator._rebuild_after_verification(
            verified_items=verified_items,
            model="test",
            previous=previous,
        )

        assert len(result.items) == 1
        assert result.items[0].description == "kept item"

    def test__rebuild_after_verification_derives_verdict_from_survivors(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Verdict comes from surviving items only, never from the previous review."""
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )

        previous = _code_review(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            items=[_make_review_item("src/main.py", "dropped item")],
        )

        result = orchestrator._rebuild_after_verification(
            verified_items=[],
            model="test",
            previous=previous,
        )

        assert result.verdict == ReviewVerdict.APPROVED.value
        assert result.items == []

    def test__is_max_turns_exceeded(self, mock_command_bus, mock_tool_factory) -> None:
        """Only MaxTurnsExceededError counts as turn exhaustion."""
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )

        assert orchestrator._is_max_turns_exceeded(
            MaxTurnsExceededError("Phase exceeded max turns (10)")
        )
        assert not orchestrator._is_max_turns_exceeded(
            AdvisorBlockedError("Advisor blocked phase after 2 blocking grades")
        )
        assert not orchestrator._is_max_turns_exceeded(
            LlmUnavailableError("Ollama unreachable")
        )

    def test_execute_with_command_bus(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test full execute flow with command bus."""
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )

        plan = _plan()

        # Make _run_phases return a result with items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(), pr_identifier_service="", review_session="", base_sha="": _outcome(
            verdict=ReviewVerdict.APPROVED,
            reason="LGTM",
            summary="Looks good",
            items=[_make_review_item("src/main.py", "fix something")],
        )

        result = orchestrator.execute(
            type("Cmd", (), {"existing_item_ids": frozenset(), "review_session": "test-session", 
                "base_sha": "",
                "plan": {"phases": plan, "methodology": "sub-agent-multi-phase"},
                "repo_path": Path("/tmp"),
                "changed_files": ["src/main.py"],
                "model": "test",
            })()
        )

        assert result.verdict == ReviewVerdict.APPROVED.value
        assert len(result.items) == 1

    def test_execute_respects_conversation_budget(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """A conversation budget caps the total peer conversations per review."""
        plan = ReviewPlan(
            phases=(
                ReviewPhase(
                    phase_id="engineer", phase_name="Engineer Review",
                    system_prompt="",
                ),
                ReviewPhase(
                    phase_id="architect", phase_name="Architecture Review",
                    system_prompt="",
                ),
            ),
            methodology="m",
            suggestions_phase_id="architect",
        )
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            max_conversations=1,
        )
        engineer_result = _phase_result(
            verdict="approved",
            items=[_make_review_item("src/main.py", "budget item")],
        )
        # The first conversation consumes the budget; the second phase must
        # never start one. Event publishes are satisfied ad hoc so they don't
        # exhaust the mock — only the conversation dispatch is budgeted.
        def dispatch(command):
            if isinstance(command, RunAgentConversationCommand):
                return engineer_result
            if isinstance(command, AggregateReviewFindingsCommand):
                return _code_review(items=list(command.items))
            return MagicMock()

        mock_command_bus.dispatch.side_effect = dispatch

        result = orchestrator.execute(
            type("Cmd", (), {"existing_item_ids": frozenset(), "review_session": "test-session",
                "base_sha": "",
                "plan": plan,
                "repo_path": Path("/tmp"),
                "changed_files": ["src/main.py"],
                "model": "test",
            })()
        )

        conversation_calls = [
            call
            for call in mock_command_bus.dispatch.call_args_list
            if isinstance(call.args[0], RunAgentConversationCommand)
        ]
        assert len(conversation_calls) == 1
        # The first phase's item is salvaged into the published review rather
        # than everything being lost to the budget stop.
        assert len(result.items) == 1
        assert result.items[0].description == "budget item"

    def test_run_phases_sources_suggestions_from_plan_suggestions_phase(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """The architect phase's llm_suggestions feed the final review's suggestions."""
        plan = ReviewPlan(
            phases=(
                ReviewPhase(
                    phase_id="engineer", phase_name="Engineer Review",
                    system_prompt="",
                ),
                ReviewPhase(
                    phase_id="architect", phase_name="Architecture Review",
                    system_prompt="",
                ),
            ),
            methodology="m",
            suggestions_phase_id="architect",
        )
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )
        engineer_result = _phase_result(
            suggestions=[{"description": "engineer suggestion"}],
        )
        architect_result = _phase_result(
            verdict="approved",
            suggestions=[{"description": "architect suggestion"}],
            praise=[{"description": "clean architecture"}],
        )
        mock_command_bus.dispatch.side_effect = [
            engineer_result,
            MagicMock(),
            architect_result,
            MagicMock(),
        ]

        result = orchestrator._run_phases(
            plan, Path("/tmp"), ["src/main.py"], "test",
        ).review

        assert [s.description for s in result.suggestions] == [
            "architect suggestion"
        ]
        assert len(result.praise) == 1
        assert result.praise[0].description == "clean architecture"

    def test_zero_items_never_publishes_changes_requested(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """A CHANGES_REQUESTED LLM verdict with no items reads as a clean approval.

        Nothing was flagged, so a blocking CHANGES_REQUESTED is incoherent;
        the empty review resolves to APPROVED instead.
        """
        plan = ReviewPlan(
            phases=(
                ReviewPhase(
                    phase_id="architect", phase_name="Architecture Review",
                    system_prompt="",
                ),
            ),
            methodology="m",
            suggestions_phase_id="architect",
        )
        orchestrator = MultiPhaseReviewOrchestratorService(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )
        architect_result = _phase_result(
            verdict="changes_requested",
            items=[],
            reason="the code is wrong",
        )
        mock_command_bus.dispatch.side_effect = [
            architect_result,
            MagicMock(),
        ]

        result = orchestrator._run_phases(
            plan, Path("/tmp"), ["src/main.py"], "test",
        ).review

        assert result.verdict == ReviewVerdict.APPROVED
        assert result.items == []
        assert result.reason == "the code is wrong"

