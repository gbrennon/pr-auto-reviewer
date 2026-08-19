"""Tests for MultiPhaseReviewOrchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from pr_auto_reviewer.application.services.multi_phase_review_orchestrator import (
    MultiPhaseReviewOrchestrator,
)
from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
from pr_auto_reviewer.domain.agent.review_plan import ReviewPlan
from pr_auto_reviewer.domain.agent.sub_review_guardrails import SubReviewGuardrails
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.messages.commands.aggregate_review_findings_command import (
    AggregateReviewFindingsCommand,
)
from pr_auto_reviewer.domain.messages.commands.verify_findings_command import (
    VerifyFindingsCommand,
)
from pr_auto_reviewer.domain.messages.events.findings_aggregated_event import (
    FindingsAggregatedEvent,
)
from pr_auto_reviewer.domain.messages.events.phase_completed_event import (
    PhaseCompletedEvent,
)


def _plan():
    """Build a ReviewPlan."""
    from pr_auto_reviewer.domain.agent.review_phase import ReviewPhase
    phases: list[ReviewPhase] = []
    phase_configs = [
        ("advisor", "Advisor Review"),
        ("engineer", "Engineer Review"),
        ("architect", "Architect Review"),
        ("security", "Security Review"),
        ("performance", "Performance Analysis"),
    ]
    for phase_id, phase_name in phase_configs:
        phases.append(
            ReviewPhase(
                phase_id=phase_id,
                phase_name=phase_name,
                system_prompt="",
            )
        )
    return tuple(phases)


def _code_review(
    verdict=ReviewVerdict.APPROVED,
    reason="",
    summary="",
    items=None,
    suggestions=None,
    praise=None,
    model_used="test",
) -> CodeReview:
    """Build a CodeReview."""
    return CodeReview(
        verdict=verdict,
        reason=reason,
        summary=summary,
        items=items or [],
        suggestions=suggestions or [],
        praise=praise or [],
        model_used=model_used,
    )


def _phase_result(
    verdict="approved",
    reason="",
    summary="",
    items=None,
    suggestions=None,
    praise=None,
) -> PhaseResult:
    """Build a PhaseResult."""
    return PhaseResult(
        items=items or [],
        llm_verdict=verdict,
        llm_reason=reason,
        llm_summary=summary,
        llm_suggestions=suggestions or [],
        llm_praise=praise or [],
    )


def _make_review_item(file_path, description) -> ReviewItem:
    """Create a review item."""
    return ReviewItem(
        file_path=file_path,
        description=description,
        severity="minor",
        category="style",
    )


class TestMultiPhaseReviewOrchestrator:
    """Tests for the MultiPhaseReviewOrchestrator."""

    def test_execute_full_retry(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test full review execution with retry logic."""
        orchestrator = MultiPhaseReviewOrchestrator(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            max_retries=2,
        )
        from types import SimpleNamespace
        plan = SimpleNamespace(phases=_plan(), methodology="sub-agent-multi-phase")
        result = orchestrator.execute(
            type("Cmd", (), {"existing_item_ids": frozenset(), 
                "plan": plan,
                "repo_path": Path("/tmp"),
                "changed_files": ["src/main.py"],
                "model": "test",
            })()
        )
        assert result is not None

    def test_execute_with_llm_unavailable(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test execution when LLM is unavailable."""
        orchestrator = MultiPhaseReviewOrchestrator(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            max_retries=1,
        )
        from types import SimpleNamespace
        plan = SimpleNamespace(phases=_plan(), methodology="sub-agent-multi-phase")

        def failing_run_phases(*args, **kwargs):
            from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
            raise LlmUnavailableError("Phase exceeded max turns (attempt 1)")

        orchestrator._run_phases = failing_run_phases
        result = orchestrator.execute(
            type("Cmd", (), {"existing_item_ids": frozenset(), 
                "plan": plan,
                "repo_path": Path("/tmp"),
                "changed_files": ["src/main.py"],
                "model": "test",
            })()
        )
        # After max retries, should return CODE_REVIEW with COMMENTED verdict
        assert result is not None
        assert result.verdict == ReviewVerdict.COMMENTED.value

    def test__run_phases_full_retry_no_items(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _run_phases_full_retry when no items are found."""
        orchestrator = MultiPhaseReviewOrchestrator(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            max_retries=3,
        )

        plan = _plan()

        # Make _run_phases return a result with no items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(): _code_review(
            verdict=ReviewVerdict.COMMENTED,
            reason="No issues found",
            summary="No issues found",
        )

        result = orchestrator._run_phases_full_retry(
            plan=plan,
            repo_path=Path("/tmp"),
            changed_files=["src/main.py"],
            model="test",
        )

        assert result.verdict == ReviewVerdict.COMMENTED.value

    def test__run_phases_full_retry_with_items(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _run_phases_full_retry when items are found."""
        orchestrator = MultiPhaseReviewOrchestrator(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            max_retries=1,
        )

        plan = _plan()

        # Make _run_phases return a result with items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(): _code_review(
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
        )

        assert result.verdict == ReviewVerdict.APPROVED.value
        assert len(result.items) == 1

    def test__run_feedback_loop(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _run_feedback_loop logic."""
        orchestrator = MultiPhaseReviewOrchestrator(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
            max_feedback_rounds=2,
        )

        plan = _plan()

        # First round returns no items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(): _code_review(
            verdict=ReviewVerdict.COMMENTED,
            reason="No issues",
            summary="No issues",
        )

        # Second round returns items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(): _code_review(
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
            previous_result=_code_review(verdict=ReviewVerdict.COMMENTED),
        )

        assert result.verdict == ReviewVerdict.APPROVED.value
        assert len(result.items) == 1

    def test__build_feedback_context(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _build_feedback_context."""
        orchestrator = MultiPhaseReviewOrchestrator(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )

        result = _code_review(
            verdict=ReviewVerdict.COMMENTED,
            reason="No issues",
            summary="No issues found",
        )

        context = orchestrator._build_feedback_context(result, 1)
        assert "Attempt #1" in context
        assert "No issues found" in context

    def test__run_phases_with_feedback(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _run_phases with initial_feedback."""
        orchestrator = MultiPhaseReviewOrchestrator(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )

        plan = _plan()

        # First run returns no items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(): _code_review(
            verdict=ReviewVerdict.COMMENTED,
            reason="No issues",
            summary="No issues",
        )

        # Second run with feedback returns items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(): _code_review(
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
        )

        assert result.verdict == ReviewVerdict.APPROVED.value

    def test__rebuild_after_verification(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _rebuild_after_verification."""
        orchestrator = MultiPhaseReviewOrchestrator(
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

    def test__rebuild_after_verification_commented_verdict(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test _rebuild_after_verification with COMMENTED verdict."""
        orchestrator = MultiPhaseReviewOrchestrator(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )

        verified_items = []
        previous = _code_review(
            verdict=ReviewVerdict.COMMENTED,
            items=[],
        )

        result = orchestrator._rebuild_after_verification(
            verified_items=verified_items,
            model="test",
            previous=previous,
        )

        assert result.verdict == ReviewVerdict.COMMENTED.value

    def test__is_max_turns_exceeded(self, mock_command_bus, mock_tool_factory) -> None:
        """Test _is_max_turns_exceeded helper."""
        orchestrator = MultiPhaseReviewOrchestrator(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )

        # Should return True - create instance with proper str
        exc = type("Exc", (), {"__str__": lambda self: "Phase exceeded max turns"})()
        assert orchestrator._is_max_turns_exceeded(exc)

        # Should return False
        assert not orchestrator._is_max_turns_exceeded(
            type("Exc", (), {"__str__": lambda self: "Other error"})()
        )

    def test_execute_with_command_bus(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """Test full execute flow with command bus."""
        orchestrator = MultiPhaseReviewOrchestrator(
            command_bus=mock_command_bus,
            tool_factory=mock_tool_factory,
        )

        plan = _plan()

        # Make _run_phases return a result with items
        orchestrator._run_phases = lambda plan, repo_path, changed_files, model, accumulated_items=None, initial_feedback="", existing_item_ids=frozenset(): _code_review(
            verdict=ReviewVerdict.APPROVED,
            reason="LGTM",
            summary="Looks good",
            items=[_make_review_item("src/main.py", "fix something")],
        )

        result = orchestrator.execute(
            type("Cmd", (), {"existing_item_ids": frozenset(), 
                "plan": {"phases": plan, "methodology": "sub-agent-multi-phase"},
                "repo_path": Path("/tmp"),
                "changed_files": ["src/main.py"],
                "model": "test",
            })()
        )

        assert result.verdict == ReviewVerdict.APPROVED.value
        assert len(result.items) == 1

    def test_run_phases_sources_suggestions_from_plan_suggestions_phase(
        self, mock_command_bus, mock_tool_factory,
    ) -> None:
        """The architect phase's llm_suggestions feed the final review's suggestions."""
        from unittest.mock import MagicMock
        from pr_auto_reviewer.domain.agent.review_phase import ReviewPhase
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
        orchestrator = MultiPhaseReviewOrchestrator(
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
        )

        assert [s.description for s in result.suggestions] == [
            "architect suggestion"
        ]
        assert len(result.praise) == 1
        assert result.praise[0].description == "clean architecture"