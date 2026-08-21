"""FindingAggregator — deduplicate and merge review items across phases."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pr_auto_reviewer.application.ports.inbound.aggregate_review_findings_use_case import (
    AggregateReviewFindingsUseCase,
)
from pr_auto_reviewer.application.ports.outbound.reason_factory_port import (
    ReasonFactoryPort,
)
from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
from pr_auto_reviewer.domain.agent.sub_review_guardrails import (
    SubReviewGuardrails,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.aggregate_review_findings_command import (
    AggregateReviewFindingsCommand,
)
from pr_auto_reviewer.domain.services.review_item_factory import ReviewItemFactory
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.review_verdict import (
    ReviewVerdict,
)


class FindingAggregator(AggregateReviewFindingsUseCase):
    """Deduplicate and merge review items across phases into a CodeReview.

    Pure domain logic — no I/O dependencies.
    """

    _DUPLICATE_SUFFIX = (
        ". This was previously identified but may have additional instances."
    )

    def __init__(self, reason_factory: ReasonFactoryPort) -> None:
        self._reason_factory = reason_factory

    def execute(
        self, command: AggregateReviewFindingsCommand
    ) -> CodeReview:
        """Deduplicate *command.items* and build a ``CodeReview``."""
        return self._merge(
            command.items,
            command.phase_result,
            command.suggestions_phase_result,
            command.model_used,
        )

    def _build_summary(self, merged: list[ReviewItem]) -> str:
        """Build a short human-readable summary from the merged items."""
        files = sorted({item.file_path for item in merged if item.file_path})
        blocking = sum(1 for item in merged if item.is_blocking)
        base = (
            f"Found {len(merged)} issue(s)"
            f" ({blocking} blocking across {len(files)} file(s))."
        )
        if files:
            base += " Files: " + ", ".join(files[:5])
        return base

    def _merge(
        self,
        items: list[ReviewItem],
        phase_result: PhaseResult | None = None,
        suggestions_phase_result: PhaseResult | None = None,
        model_used: str = "",
    ) -> CodeReview:
        """Deduplicate *items* and build a ``CodeReview``.

        When *phase_result* is provided, its ``llm_reason`` is used as
        a fallback when the merged item list is empty, and its
        ``llm_suggestions`` / ``llm_praise`` are parsed into the
        corresponding domain entities. When
        ``suggestions_phase_result`` is provided, its ``llm_suggestions``
        are the suggestion source instead (praise, reason, summary, and
        verdict still come from ``phase_result``).
        """
        seen: set[tuple[str, str, str, str]] = set()
        merged: list[ReviewItem] = []

        for item in items:
            desc = item.description
            if desc.endswith(self._DUPLICATE_SUFFIX):
                desc = desc.removesuffix(self._DUPLICATE_SUFFIX)
            key = (
                item.file_path or "",
                str(item.severity),
                str(item.category),
                desc,
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)

        verdict = SubReviewGuardrails().verdict_for(merged)

        reason = self._reason_factory.make(merged)
        summary = ""
        suggestions: list[ReviewItem] = []
        praise: list[ReviewItem] = []

        if phase_result is not None:
            coerced = ReviewVerdict.coerce(phase_result.llm_verdict)

            if coerced is not None:
                verdict = coerced

            if not reason and phase_result.llm_reason:
                reason = phase_result.llm_reason

            if phase_result.llm_summary:
                summary = phase_result.llm_summary

            suggestion_source = suggestions_phase_result or phase_result
            for s in suggestion_source.llm_suggestions:
                suggestions.append(ReviewItem(
                    severity=ItemSeverity.INFO,
                    category=IssueCategory.GENERAL,
                    file_path=s.get("file", ""),
                    description=s.get("description", ""),
                    line=s.get("line", ""),
                    id=s.get("id", "") or ReviewItemFactory._generate_id(),
                    current_code=s.get("current_code", ""),
                    suggested_fix=s.get("suggested_fix", ""),
                ))

            for p in phase_result.llm_praise:
                praise.append(ReviewItem(
                    severity=ItemSeverity.INFO,
                    category=IssueCategory.GENERAL,
                    file_path=p.get("file", ""),
                    description=p.get("description", ""),
                    line="",
                    id="",
                    current_code="",
                    suggested_fix=p.get("description", ""),
                ))

        if not summary and merged:
            summary = self._build_summary(merged)

        return CodeReview(
            verdict=verdict,
            reason=reason,
            summary=summary,
            items=merged,
            suggestions=suggestions,
            praise=praise,
            model_used=model_used,
        )
