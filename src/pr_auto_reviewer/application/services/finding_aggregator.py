"""FindingAggregator — deduplicate and merge review items across phases."""

from __future__ import annotations

from pr_auto_reviewer.domain.messages.commands.aggregate_review_findings_command import (
    AggregateReviewFindingsCommand,
)
from pr_auto_reviewer.application.ports.inbound.aggregate_review_findings_use_case import (
    AggregateReviewFindingsUseCase,
)
from pr_auto_reviewer.application.ports.outbound.reason_builder_port import (
    ReasonBuilderPort,
)
from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.entities.review_praise import ReviewPraise
from pr_auto_reviewer.domain.entities.review_suggestion import (
    ReviewSuggestion,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
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

    def __init__(self, reason_builder: ReasonBuilderPort) -> None:
        self._reason_builder = reason_builder

    def execute(
        self, command: AggregateReviewFindingsCommand
    ) -> CodeReview:
        """Deduplicate *command.items* and build a ``CodeReview``."""
        return self._merge(
            command.items, command.phase_result, command.model_used
        )

    @staticmethod
    def _build_summary(merged: list[ReviewItem]) -> str:
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
        model_used: str = "",
    ) -> CodeReview:
        """Deduplicate *items* and build a ``CodeReview``.

        When *phase_result* is provided, its ``llm_reason`` is used as
        a fallback when the merged item list is empty, and its
        ``llm_suggestions`` / ``llm_praise`` are parsed into the
        corresponding domain entities.
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

        for i, item in enumerate(merged, 1):
            object.__setattr__(item, "number", i)

        if not merged:
            verdict = ReviewVerdict.APPROVED
        elif any(item.is_blocking for item in merged):
            verdict = ReviewVerdict.CHANGES_REQUESTED
        else:
            verdict = ReviewVerdict.APPROVED

        reason = self._reason_builder.build(merged)
        summary = ""
        suggestions: list[ReviewSuggestion] = []
        praise: list[ReviewPraise] = []

        if phase_result is not None:
            coerced = ReviewVerdict.coerce(phase_result.llm_verdict)
            if coerced is not None:
                verdict = coerced
            if not reason and phase_result.llm_reason:
                reason = phase_result.llm_reason
            if phase_result.llm_summary:
                summary = phase_result.llm_summary
            for s in phase_result.llm_suggestions:
                suggestions.append(ReviewSuggestion(
                    file=s.get("file", ""),
                    line=s.get("line", ""),
                    description=s.get("description", ""),
                ))
            for p in phase_result.llm_praise:
                praise.append(ReviewPraise(
                    file=p.get("file", ""),
                    description=p.get("description", ""),
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
