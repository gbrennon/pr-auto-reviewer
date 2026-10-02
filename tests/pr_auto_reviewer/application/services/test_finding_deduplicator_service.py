from pr_auto_reviewer.application.services.finding_deduplicator_service import (
    FindingDeduplicatorService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity


def _finding(
    description: str,
    severity: ItemSeverity = ItemSeverity.MINOR,
    line: str = "",
    current_code: str = "",
) -> ReviewItem:
    return ReviewItem(
        id="finding",
        severity=severity,
        category=IssueCategory.BUG,
        file_path="src/main.py",
        description=description,
        line=line,
        current_code=current_code,
    )


class TestFindingDeduplicatorService:
    """Behavior of FindingDeduplicatorService.deduplicate."""

    def test_deduplicate_merges_identical_findings(self) -> None:
        findings = [_finding("Repeated issue"), _finding("Repeated issue")]

        merged = FindingDeduplicatorService().deduplicate(findings)

        assert len(merged) == 1

    def test_deduplicate_keeps_the_highest_severity(self) -> None:
        findings = [
            _finding("Repeated issue", ItemSeverity.MINOR),
            _finding("Repeated issue", ItemSeverity.MAJOR),
        ]

        merged = FindingDeduplicatorService().deduplicate(findings)

        assert merged[0].severity == ItemSeverity.MAJOR

    def test_deduplicate_merges_overlapping_code(self) -> None:
        findings = [
            _finding("First issue", current_code="value = 1"),
            _finding("Second issue", current_code="value = 1\nreturn value"),
        ]

        merged = FindingDeduplicatorService().deduplicate(findings)

        assert len(merged) == 1

    def test_deduplicate_merges_overlapping_lines_in_same_category(self) -> None:
        findings = [
            _finding("First issue", line="10-12"),
            _finding("Second issue", line="12-14"),
        ]

        merged = FindingDeduplicatorService().deduplicate(findings)

        assert len(merged) == 1
