"""FindingDeduplicatorService — merge duplicate review findings."""

from __future__ import annotations

from typing import ClassVar

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity


class FindingDeduplicatorService:
    """Deduplicate review findings while preserving the strongest evidence."""

    _DUPLICATE_SUFFIX = (
        ". This was previously identified but may have additional instances."
    )
    _SEVERITY_RANKS: ClassVar[dict[ItemSeverity, int]] = {
        ItemSeverity.CRITICAL: 4,
        ItemSeverity.MAJOR: 3,
        ItemSeverity.MINOR: 2,
        ItemSeverity.INFO: 1,
    }

    def deduplicate(self, items: list[ReviewItem]) -> list[ReviewItem]:
        """Return findings with duplicate entries merged in input order."""
        merged: list[ReviewItem] = []
        for item in items:
            match_index = next(
                (
                    index
                    for index, existing in enumerate(merged)
                    if self._is_duplicate(existing, item)
                ),
                None,
            )
            if match_index is None:
                merged.append(item)
                continue
            merged[match_index] = self._merge_duplicate(merged[match_index], item)
        return merged

    def _is_duplicate(self, first: ReviewItem, second: ReviewItem) -> bool:
        """Return whether two findings describe the same issue in one file."""
        if not first.file_path or first.file_path != second.file_path:
            return False

        first_description = first.description.removesuffix(
            self._DUPLICATE_SUFFIX
        ).strip()
        second_description = second.description.removesuffix(
            self._DUPLICATE_SUFFIX
        ).strip()
        if first_description and first_description == second_description:
            return True

        first_code = first.current_code.strip()
        second_code = second.current_code.strip()
        if first_code and second_code and (
            first_code in second_code or second_code in first_code
        ):
            return True

        if first.line and second.line:
            first_lines = self._parse_lines(first.line)
            second_lines = self._parse_lines(second.line)
            if first_lines.intersection(second_lines) and (
                (first_code and second_code) or first.category == second.category
            ):
                return True

        return False

    def _merge_duplicate(
        self, existing: ReviewItem, new: ReviewItem
    ) -> ReviewItem:
        """Keep the higher-severity finding and enrich it with available evidence."""
        existing_rank = self._SEVERITY_RANKS.get(existing.severity, 0)
        new_rank = self._SEVERITY_RANKS.get(new.severity, 0)
        primary = new if new_rank > existing_rank else existing
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

    def _parse_lines(self, line_text: str) -> set[int]:
        """Parse comma-separated line numbers and ranges."""
        lines: set[int] = set()
        for part in line_text.split(","):
            normalized_part = part.strip()
            if "-" in normalized_part:
                start_text, _, end_text = normalized_part.partition("-")
                try:
                    start, end = int(start_text), int(end_text)
                except ValueError:
                    continue
                lines.update(range(min(start, end), max(start, end) + 1))
                continue
            if normalized_part.isdigit():
                lines.add(int(normalized_part))
        return lines
