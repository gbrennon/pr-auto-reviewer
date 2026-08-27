"""FindingAggregatorService — deduplicate and merge review items across phases."""

from __future__ import annotations

from pr_auto_reviewer.application.ports.inbound.aggregate_review_findings_port import (
    AggregateReviewFindingsPort,
)
from pr_auto_reviewer.application.ports.outbound.reason_factory_port import (
    ReasonFactoryPort,
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

    _DUPLICATE_SUFFIX = (
        ". This was previously identified but may have additional instances."
    )
    _SEVERITY_RANKS = {
        ItemSeverity.CRITICAL: 4,
        ItemSeverity.MAJOR: 3,
        ItemSeverity.MINOR: 2,
        ItemSeverity.INFO: 1,
    }

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

    def _reason_for_merged(self, merged: list[ReviewItem]) -> str:
        """Return a descriptive reason grounded in the merged findings."""
        if not merged:
            return "No issues found."
        blocking = [item for item in merged if item.is_blocking]
        target = blocking[0] if blocking else merged[0]
        desc = target.description.strip()
        sev = str(target.severity).lower()
        file_path = target.file_path.strip()
        file_str = f" in {file_path}" if file_path else ""
        if desc:
            return f"Identified {sev} issue{file_str}: {desc}"
        return self._reason_factory.make(merged)

    def _parse_lines(self, line_str: str) -> set[int]:
        """Parse line numbers or ranges into a set of line integers."""
        lines: set[int] = set()
        for part in line_str.split(","):
            part = part.strip()
            if "-" in part:
                start_s, _, end_s = part.partition("-")
                try:
                    start, end = int(start_s), int(end_s)
                    lines.update(range(min(start, end), max(start, end) + 1))
                except ValueError:
                    pass
            elif part.isdigit():
                lines.add(int(part))
        return lines

    def _is_duplicate_finding(self, a: ReviewItem, b: ReviewItem) -> bool:
        """Return True when two findings describe the same issue in the same file."""
        if not a.file_path or a.file_path != b.file_path:
            return False

        desc_a = a.description.removesuffix(self._DUPLICATE_SUFFIX).strip()
        desc_b = b.description.removesuffix(self._DUPLICATE_SUFFIX).strip()
        if desc_a and desc_a == desc_b:
            return True

        code_a = a.current_code.strip()
        code_b = b.current_code.strip()
        if code_a and code_b and (code_a in code_b or code_b in code_a):
            return True

        if a.line and b.line:
            lines_a = self._parse_lines(a.line)
            lines_b = self._parse_lines(b.line)
            if lines_a.intersection(lines_b) and (code_a and code_b or a.category == b.category):
                return True

        return False
    def _merge_duplicate(self, existing: ReviewItem, new: ReviewItem) -> ReviewItem:
        """Keep the higher severity item, enriching with better snippets if available."""
        rank_existing = self._SEVERITY_RANKS.get(existing.severity, 0)
        rank_new = self._SEVERITY_RANKS.get(new.severity, 0)
        primary = new if rank_new > rank_existing else existing
        secondary = existing if primary is new else new

        return ReviewItem(
            severity=primary.severity,
            category=primary.category,
            file_path=primary.file_path,
            description=primary.description,
            line=primary.line or secondary.line,
            id=primary.id or secondary.id,
            current_code=primary.current_code or secondary.current_code,
            suggested_fix=primary.suggested_fix or secondary.suggested_fix,
        )

    def _deduplicate(self, items: list[ReviewItem]) -> list[ReviewItem]:
        """Deduplicate items by key, code overlap, and line overlap."""
        merged: list[ReviewItem] = []
        for item in items:
            match_index: int | None = None
            for idx, existing in enumerate(merged):
                if self._is_duplicate_finding(existing, item):
                    match_index = idx
                    break
            if match_index is not None:
                merged[match_index] = self._merge_duplicate(merged[match_index], item)
            else:
                merged.append(item)
        return merged

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
        merged = self._deduplicate(items)
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
            for s in suggestion_source.llm_suggestions:
                suggestions.append(ReviewItem(
                    severity=ItemSeverity.INFO,
                    category=IssueCategory.GENERAL,
                    file_path=s.get("file", ""),
                    description=s.get("description", ""),
                    line=s.get("line", ""),
                    id=s.get("id", "") or ReviewItemFactory.generate_id(),
                    current_code=s.get("current_code", ""),
                    suggested_fix=s.get("suggested_fix", ""),
                ))

            praise_source = suggestions_phase_result or phase_result
            praise_entries = list(praise_source.llm_praise)
            if phase_result is not praise_source:
                for p in phase_result.llm_praise:
                    if p not in praise_entries:
                        praise_entries.append(p)

            for p in praise_entries:
                praise.append(ReviewItem(
                    severity=ItemSeverity.INFO,
                    category=IssueCategory.GENERAL,
                    file_path=p.get("file", ""),
                    description=p.get("description", ""),
                    line="",
                    id=p.get("id", "") or ReviewItemFactory.generate_id(),
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
