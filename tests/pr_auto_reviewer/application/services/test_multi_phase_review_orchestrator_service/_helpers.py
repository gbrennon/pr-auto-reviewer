"""Shared helpers, fixtures, and imports for the split test modules."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import pytest as _pytest

from pr_auto_reviewer.application.services.multi_phase_review_orchestrator_service import (
    MultiPhaseReviewOrchestratorService,
    _PhaseRunOutcome,
)
from pr_auto_reviewer.application.services.turn_parser_service import TurnParserService
from pr_auto_reviewer.domain.entities.engineer_agent import EngineerAgent
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions.advisor_blocked_error import (
    AdvisorBlockedError,
)
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.exceptions.max_turns_exceeded_error import (
    MaxTurnsExceededError,
)
from pr_auto_reviewer.domain.exceptions.review_verdict_error import ReviewVerdictError
from pr_auto_reviewer.domain.messages.commands.aggregate_review_findings_command import (
    AggregateReviewFindingsCommand,
)
from pr_auto_reviewer.domain.messages.commands.parse_review_turn_command import (
    ParseReviewTurnCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_agent_conversation_command import (
    RunAgentConversationCommand,
)
from pr_auto_reviewer.domain.value_objects.advisor_directive import (
    AdvisorDirective,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.review_phase import ReviewPhase
from pr_auto_reviewer.domain.value_objects.review_plan import ReviewPlan
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.value_objects.sub_agent_grade import (
    SubAgentGrade,
)
from pr_auto_reviewer.domain.value_objects.turn_parse_result import TurnParseResult
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)


def _plan():
    """Build a ReviewPlan."""
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


def _outcome(dropped_findings: int = 0, **kwargs):
    """Wrap a CodeReview in the orchestrator's phase-run outcome."""
    return _PhaseRunOutcome(
        review=_code_review(**kwargs),
        dropped_findings=dropped_findings,
    )


def _code_review(
    verdict=ReviewVerdict.APPROVED,
    reason="test reason",
    summary="test summary",
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


__all__ = ['AdvisorBlockedError', 'AdvisorDirective', 'AggregateReviewFindingsCommand', 'CodeReview', 'EngineerAgent', 'InMemoryCommandBus', 'IssueCategory', 'ItemSeverity', 'LlmUnavailableError', 'MagicMock', 'MaxTurnsExceededError', 'MultiPhaseReviewOrchestratorService', 'ParseReviewTurnCommand', 'Path', 'PhaseResult', 'ReviewItem', 'ReviewPhase', 'ReviewPlan', 'ReviewResponseParser', 'ReviewVerdict', 'ReviewVerdictError', 'RunAgentConversationCommand', 'SimpleNamespace', 'SubAgentGrade', 'TurnParseResult', 'TurnParserService', '_PhaseRunOutcome', '_code_review', '_make_review_item', '_outcome', '_phase_result', '_plan', '_pytest', 'annotations', 'pytest']
