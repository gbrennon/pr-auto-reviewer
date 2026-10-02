"""FindingAggregatorService — deduplicate and merge review items across phases."""

from __future__ import annotations

from pathlib import Path

from pr_auto_reviewer.application.ports.inbound.aggregate_review_findings_port import (
    AggregateReviewFindingsPort,
)
from pr_auto_reviewer.application.ports.outbound.reason_factory_port import (
    ReasonFactoryPort,
)
from pr_auto_reviewer.application.services.finding_deduplicator_service import (
    FindingDeduplicatorService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.aggregate_review_findings_command import (
    AggregateReviewFindingsCommand,
)
from pr_auto_reviewer.domain.services.review_item_factory import ReviewItemFactory
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.review_verdict import (
    ReviewVerdict,
)
from pr_auto_reviewer.domain.value_objects.sub_review_guardrails import (
    SubReviewGuardrails,
)


class FindingAggregatorService(AggregateReviewFindingsPort):
    """Deduplicate and merge review items across phases into a CodeReview.

    Pure domain logic — no I/O dependencies.
    """

    def __init__(
        self,
        reason_factory: ReasonFactoryPort,
        deduplicator: FindingDeduplicatorService | None = None,
    ) -> None:
        self._reason_factory = reason_factory
        self._deduplicator = deduplicator or FindingDeduplicatorService()

    def execute(
        self, command: AggregateReviewFindingsCommand
    ) -> CodeReview:
        """Deduplicate *command.items* and build a ``CodeReview``."""
        return self._merge(
            command.items,
            command.phase_result,
            command.suggestions_phase_result,
            command.model_used,
            command.repo_path,
            command.changed_files,
        )

    def _normalize_citation_path(
        self,
        file_path: str,
        repo_path: Path | None,
        changed_files: list[str] | None,
        *,
        drop_unmapped: bool,
    ) -> str | None:
        """Normalize a citation path or apply the invalid-citation policy."""
        normalized = ReviewItemFactory._normalize_file_path(
            file_path, repo_path, changed_files,
        )
        if normalized is not None:
            return normalized
        return None if drop_unmapped else ""

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

    def _reason_for_merged(self, merged: list[ReviewItem]) -> str:
        """Return a descriptive reason grounded in the merged findings."""
        if not merged:
            return "No issues found."
        blocking = [item for item in merged if item.is_blocking]
        target = blocking[0] if blocking else merged[0]
        desc = target.description.strip()
        sev = str(target.severity).lower()
        file_path = (target.file_path or "").strip()
        file_str = f" in {file_path}" if file_path else ""
        if desc:
            return f"Identified {sev} issue{file_str}: {desc}"
        return self._reason_factory.make(merged)

    def _merge(
        self,
        items: list[ReviewItem],
        phase_result: PhaseResult | None = None,
        suggestions_phase_result: PhaseResult | None = None,
        model_used: str = "",
        repo_path: Path | None = None,
        changed_files: list[str] | None = None,
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
        merged = self._deduplicator.deduplicate(items)
        verdict = SubReviewGuardrails().verdict_for(merged)

        phase_items_count = len(phase_result.items) if phase_result is not None else 0
        phase_has_blocking = (
            any(i.is_blocking for i in phase_result.items)
            if phase_result is not None
            else False
        )
        merged_has_blocking = any(i.is_blocking for i in merged)

        if (
            phase_result is not None
            and phase_result.llm_summary
            and len(merged) == phase_items_count
            and merged_has_blocking == phase_has_blocking
        ):
            summary = phase_result.llm_summary
        elif merged:
            summary = self._build_summary(merged)
        else:
            summary = (
                phase_result.llm_summary
                if (phase_result is not None and phase_result.llm_summary)
                else ""
            )

        if (
            phase_result is not None
            and phase_result.llm_reason
            and (not merged_has_blocking or phase_has_blocking)
            and (len(merged) == phase_items_count or not merged)
        ):
            reason = phase_result.llm_reason
        elif merged:
            reason = self._reason_for_merged(merged)
        else:
            reason = (
                phase_result.llm_reason
                if (phase_result is not None and phase_result.llm_reason)
                else self._reason_factory.make(merged)
            )

        suggestions: list[ReviewItem] = []
        praise: list[ReviewItem] = []

        if phase_result is not None:
            coerced = ReviewVerdict.coerce(phase_result.llm_verdict)

            if coerced is not None:
                verdict = coerced

            suggestion_source = suggestions_phase_result or phase_result
            for suggestion in suggestion_source.llm_suggestions:
                normalized_path = self._normalize_citation_path(
                    suggestion.get("file", ""),
                    repo_path,
                    changed_files,
                    drop_unmapped=False,
                )
                suggestions.append(ReviewItem(
                    severity=ItemSeverity.INFO,
                    category=IssueCategory.GENERAL,
                    file_path=normalized_path or "",
                    description=suggestion.get("description", ""),
                    line=suggestion.get("line", ""),
                    id=suggestion.get("id", "") or ReviewItemFactory.generate_id(),
                    current_code=suggestion.get("current_code", ""),
                    suggested_fix=suggestion.get("suggested_fix", ""),
                ))

            praise_source = suggestions_phase_result or phase_result
            praise_entries = list(praise_source.llm_praise)
            if phase_result is not praise_source:
                for praise_entry in phase_result.llm_praise:
                    if praise_entry not in praise_entries:
                        praise_entries.append(praise_entry)

            for praise_entry in praise_entries:
                normalized_path = self._normalize_citation_path(
                    praise_entry.get("file", ""),
                    repo_path,
                    changed_files,
                    drop_unmapped=True,
                )
                if normalized_path is None:
                    continue
                praise.append(ReviewItem(
                    severity=ItemSeverity.INFO,
                    category=IssueCategory.GENERAL,
                    file_path=normalized_path,
                    description=praise_entry.get("description", ""),
                    line="",
                    id=praise_entry.get("id", "") or ReviewItemFactory.generate_id(),
                    current_code="",
                    suggested_fix="",
                ))


        if not summary:
            summary = self._build_summary(merged)
        if not reason:
            reason = self._reason_factory.make(merged)
        return CodeReview(
            verdict=verdict,
            reason=reason,
            summary=summary,
            items=merged,
            suggestions=suggestions,
            praise=praise,
            model_used=model_used,
        )
