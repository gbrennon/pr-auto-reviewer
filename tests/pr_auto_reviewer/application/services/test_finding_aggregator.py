"""Tests for FindingAggregator application service."""

from pr_auto_reviewer.application.services.finding_aggregator import (
    FindingAggregator,
)
from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.aggregate_review_findings_command import (
    AggregateReviewFindingsCommand,
)
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


def _review_item(
    description: str,
    *,
    item_id: str = "id-1",
    severity: ItemSeverity = ItemSeverity.MINOR,
    category: IssueCategory = IssueCategory.BUG,
    file_path: str | None = "x.py",
) -> ReviewItem:
    return ReviewItem(
        id=item_id,
        severity=severity,
        category=category,
        file_path=file_path,
        description=description,
    )


class TestFindingAggregator:
    """Behaviour of FindingAggregator.execute(command) -> CodeReview."""

    def test_execute_generates_summary_from_merged_items(
        self, mock_reason_factory,
    ) -> None:
        items = [
            _review_item(
                "Off-by-one in loop",
                severity=ItemSeverity.MAJOR,
                file_path="src/utils.py",
            ),
            _review_item("Use f-strings", file_path="src/main.py"),
        ]
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregator(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, model_used="m")
        )

        assert review.summary == (
            "Found 2 issue(s) (1 blocking across 2 file(s)). "
            "Files: src/main.py, src/utils.py"
        )
        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_execute_deduplicates_identical_items(
        self, mock_reason_factory,
    ) -> None:
        items = [
            _review_item("Off-by-one in loop"),
            _review_item("Off-by-one in loop"),
        ]
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregator(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items)
        )

        assert len(review.items) == 1
        assert review.items[0].id  # ID is generated

    def test_duplicate_suffix_is_stripped_before_dedup(
        self, mock_reason_factory,
    ) -> None:
        items = [
            _review_item("Off-by-one in loop"),
            _review_item(
                "Off-by-one in loop"
                ". This was previously identified but may have additional instances."
            ),
        ]
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregator(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items)
        )

        assert len(review.items) == 1

    def test_blocking_item_forces_changes_requested(
        self, mock_reason_factory,
    ) -> None:
        items = [_review_item("SQL injection", category=IssueCategory.SECURITY)]
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregator(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items)
        )

        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_non_blocking_items_yield_approved(
        self, mock_reason_factory,
    ) -> None:
        items = [
            _review_item("Use f-strings", severity=ItemSeverity.INFO, category=IssueCategory.STYLE),
        ]
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregator(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items)
        )

        assert review.verdict == ReviewVerdict.APPROVED

    def test_empty_items_yield_approved_with_empty_summary(
        self, mock_reason_factory,
    ) -> None:
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregator(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=[])
        )

        assert review.verdict == ReviewVerdict.APPROVED
        assert review.summary == ""
        assert review.items == []

    def test_phase_result_summary_takes_precedence(
        self, mock_reason_factory,
    ) -> None:
        items = [_review_item("Off-by-one in loop")]
        phase_result = PhaseResult(items=items, llm_summary="LLM summary")
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregator(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, phase_result=phase_result)
        )

        assert review.summary == "LLM summary"

    def test_phase_result_verdict_is_coerced(
        self, mock_reason_factory,
    ) -> None:
        items = [_review_item("Use f-strings")]
        phase_result = PhaseResult(items=items, llm_verdict="changes requested")
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregator(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, phase_result=phase_result)
        )

        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_phase_result_suggestions_and_praise_are_parsed(
        self, mock_reason_factory,
    ) -> None:
        items = [_review_item("Off-by-one in loop")]
        phase_result = PhaseResult(
            items=items,
            llm_suggestions=[{"file": "x.py", "line": "3", "description": "Add bounds check"}],
            llm_praise=[{"file": "x.py", "description": "Clean structure"}],
        )
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregator(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, phase_result=phase_result)
        )

        assert len(review.suggestions) == 1
        assert review.suggestions[0].description == "Add bounds check"
        assert review.suggestions[0].file_path == "x.py"
        assert len(review.praise) == 1
        assert review.praise[0].description == "Clean structure"

    def test_phase_result_reason_used_when_builder_returns_empty(
        self, mock_reason_factory,
    ) -> None:
        items = [_review_item("Off-by-one in loop")]
        phase_result = PhaseResult(items=items, llm_reason="LLM reason")
        mock_reason_factory.make.return_value = ""
        aggregator = FindingAggregator(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, phase_result=phase_result)
        )

        assert review.reason == "LLM reason"

    def test_suggestions_come_from_suggestions_phase_result(
        self, mock_reason_factory,
    ) -> None:
        """suggestions_phase_result feeds suggestions; verdict/reason/summary/praise stay on phase_result."""
        items = [_review_item("Off-by-one in loop")]
        phase_result = PhaseResult(
            items=items,
            llm_verdict="approved",
            llm_summary="From last phase",
            llm_suggestions=[{"description": "last phase suggestion"}],
            llm_praise=[{"description": "last phase praise"}],
        )
        architect_result = PhaseResult(
            llm_suggestions=[{"description": "architect suggestion"}],
        )
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregator(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(
                items=items,
                phase_result=phase_result,
                suggestions_phase_result=architect_result,
            )
        )

        assert [s.description for s in review.suggestions] == [
            "architect suggestion"
        ]
        assert len(review.praise) == 1
        assert review.praise[0].description == "last phase praise"
        assert review.summary == "From last phase"
        assert review.verdict == ReviewVerdict.APPROVED
