"""MultiPhaseReviewOrchestratorService — run a multi-phase review plan with retry and feedback."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pr_auto_reviewer.application.ports.inbound.assess_phase_port import (
    AssessPhasePort,
)
from pr_auto_reviewer.application.ports.inbound.brief_next_phase_port import (
    BriefNextPhasePort,
)
from pr_auto_reviewer.application.ports.inbound.run_multi_phase_review_port import (
    RunMultiPhaseReviewPort,
)
from pr_auto_reviewer.application.ports.outbound.command_bus_port import (
    CommandBusPort,
)
from pr_auto_reviewer.application.services.identifier_grounding_filter_service import (
    IdentifierGroundingFilterService,
)
from pr_auto_reviewer.application.services.pr_identifier_service import (
    PRIdentifierService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions.advisor_blocked_error import (
    AdvisorBlockedError,
)
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.exceptions.max_turns_exceeded_error import (
    MaxTurnsExceededError,
)
from pr_auto_reviewer.domain.exceptions.review_budget_exhausted_error import (
    ReviewBudgetExhaustedError,
)
from pr_auto_reviewer.domain.exceptions.review_verdict_error import (
    ReviewVerdictError,
)
from pr_auto_reviewer.domain.messages.commands.aggregate_review_findings_command import (
    AggregateReviewFindingsCommand,
)
from pr_auto_reviewer.domain.messages.commands.audit_remediation_command import (
    AuditRemediationCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_agent_conversation_command import (
    RunAgentConversationCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
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
from pr_auto_reviewer.domain.value_objects.advisor_directive import (
    AdvisorDirective,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.review_phase import ReviewPhase
from pr_auto_reviewer.domain.value_objects.review_plan import ReviewPlan
from pr_auto_reviewer.domain.value_objects.review_verdict import (
    ReviewVerdict,
)
from pr_auto_reviewer.domain.value_objects.sub_review_guardrails import (
    SubReviewGuardrails,
)
from pr_auto_reviewer.infrastructure.templates.conversation_renderers import (
    AdvisorCorrectionRenderer,
    FeedbackContextRenderer,
    PhasePromptRenderer,
)

logger = logging.getLogger(__name__)


_FINDINGS_MARKER = "__PREVIOUS_FINDINGS__"


__all__ = ['_FINDINGS_MARKER', 'AdvisorBlockedError', 'AdvisorCorrectionRenderer', 'AdvisorDirective', 'AggregateReviewFindingsCommand', 'AuditRemediationCommand', 'Any', 'AssessPhasePort', 'BriefNextPhasePort', 'Callable', 'CodeReview', 'CommandBusPort', 'FeedbackContextRenderer', 'FindingsAggregatedEvent', 'IdentifierGroundingFilterService', 'IssueCategory', 'ItemSeverity', 'LlmUnavailableError', 'MaxTurnsExceededError', 'PRIdentifierService', 'Path', 'PhaseCompletedEvent', 'PhasePromptRenderer', 'PhaseResult', 'ReviewBudgetExhaustedError', 'ReviewItem', 'ReviewPhase', 'ReviewPlan', 'ReviewVerdict', 'ReviewVerdictError', 'RunAgentConversationCommand', 'RunMultiPhaseReviewCommand', 'RunMultiPhaseReviewPort', 'SubReviewGuardrails', 'VerifyFindingsCommand', 'annotations', 'cast', 'dataclass', 'json', 'logger', 'logging']
