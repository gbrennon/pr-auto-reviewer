"""Tests for FindingAggregatorService application service."""

from pr_auto_reviewer.application.services.finding_aggregator_service import (
    FindingAggregatorService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.aggregate_review_findings_command import (
    AggregateReviewFindingsCommand,
)
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
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
    """Behaviour of FindingAggregatorService.execute(command) -> CodeReview."""

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
        aggregator = FindingAggregatorService(mock_reason_factory)

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
        aggregator = FindingAggregatorService(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, model_used="test model")
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
        aggregator = FindingAggregatorService(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, model_used="test model")
        )

        assert len(review.items) == 1

    def test_blocking_item_forces_changes_requested(
        self, mock_reason_factory,
    ) -> None:
        items = [_review_item("SQL injection", category=IssueCategory.SECURITY)]
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregatorService(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, model_used="test model")
        )

        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_non_blocking_items_yield_approved(
        self, mock_reason_factory,
    ) -> None:
        items = [
            _review_item("Use f-strings", severity=ItemSeverity.INFO, category=IssueCategory.STYLE),
        ]
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregatorService(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, model_used="test model")
        )

        assert review.verdict == ReviewVerdict.APPROVED

    def test_empty_items_yield_approved_with_populated_summary(
        self, mock_reason_factory,
    ) -> None:
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregatorService(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=[], model_used="test model")
        )

        assert review.verdict == ReviewVerdict.APPROVED
        assert review.summary == "Found 0 issue(s) (0 blocking across 0 file(s))."
        assert review.items == []

    def test_phase_result_summary_takes_precedence(
        self, mock_reason_factory,
    ) -> None:
        items = [_review_item("Off-by-one in loop")]
        phase_result = PhaseResult(items=items, llm_summary="LLM summary")
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregatorService(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, phase_result=phase_result, model_used="test model")
        )

        assert review.summary == "LLM summary"

    def test_phase_result_verdict_is_coerced(
        self, mock_reason_factory,
    ) -> None:
        items = [_review_item("Use f-strings")]
        phase_result = PhaseResult(items=items, llm_verdict="changes requested")
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregatorService(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, phase_result=phase_result, model_used="test model")
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
        aggregator = FindingAggregatorService(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, phase_result=phase_result, model_used="test model")
        )

        assert len(review.suggestions) == 1
        assert review.suggestions[0].description == "Add bounds check"
        assert review.suggestions[0].file_path == "x.py"
        assert len(review.praise) == 1
        assert review.praise[0].description == "Clean structure"

    def test_phase_result_paths_are_normalized_before_review_creation(
        self, mock_reason_factory, tmp_path,
    ) -> None:
        repo = tmp_path / "repo"
        source_file = repo / "src/main.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("x = 1\n")
        absolute_path = "/cache/clones/repo/src/main.py"
        items = [_review_item("Off-by-one in loop")]
        phase_result = PhaseResult(
            items=items,
            llm_suggestions=[
                {
                    "file": absolute_path,
                    "line": "1",
                    "description": "Add bounds check",
                },
            ],
            llm_praise=[
                {
                    "file": absolute_path,
                    "description": "Clean structure",
                },
            ],
        )
        mock_reason_factory.make.return_value = "Stub reason"
        aggregator = FindingAggregatorService(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(
                items=items,
                phase_result=phase_result,
                model_used="test model",
                repo_path=repo,
                changed_files=["src/main.py"],
            )
        )

        assert review.suggestions[0].file_path == "src/main.py"
        assert review.praise[0].file_path == "src/main.py"

    def test_phase_result_reason_used_when_builder_returns_empty(
        self, mock_reason_factory,
    ) -> None:
        items = [_review_item("Off-by-one in loop")]
        phase_result = PhaseResult(items=items, llm_reason="LLM reason")
        mock_reason_factory.make.return_value = ""
        aggregator = FindingAggregatorService(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, phase_result=phase_result, model_used="test model")
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
        aggregator = FindingAggregatorService(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(
                items=items,
                phase_result=phase_result,
                suggestions_phase_result=architect_result,
                model_used="test model",
            )
        )

        assert [s.description for s in review.suggestions] == [
            "architect suggestion"
        ]
        assert len(review.praise) == 1
        assert review.praise[0].description == "last phase praise"
        assert review.summary == "From last phase"

    def test_phase_result_llm_reason_takes_precedence_over_factory(
        self, mock_reason_factory,
    ) -> None:
        items = [_review_item("Off-by-one in loop")]
        phase_result = PhaseResult(items=items, llm_reason="Deep model explanation")
        mock_reason_factory.make.return_value = "Generic count reason"
        aggregator = FindingAggregatorService(mock_reason_factory)

        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=items, phase_result=phase_result, model_used="test model")
        )

        assert review.reason == "Deep model explanation"
        assert review.verdict == ReviewVerdict.APPROVED

    def test_deduplicate_overlapping_code_snippets_keeps_higher_severity(
        self, mock_reason_factory,
    ) -> None:
        item1 = ReviewItem(
            id="item-1",
            severity=ItemSeverity.CRITICAL,
            category=IssueCategory.BUG,
            file_path="src/validator.py",
            line="42",
            description="Intentional None attribute access bug",
            current_code="        # BUG comment\n        _ = self_level.nonexistent_attribute",
            suggested_fix="        if self_level is None:\n            raise ArchitectureError()",
        )
        item2 = ReviewItem(
            id="item-2",
            severity=ItemSeverity.MINOR,
            category=IssueCategory.MAINTAINABILITY,
            file_path="src/validator.py",
            line="42-61",
            description="Unintentional exception raised by accessing nonexistent_attribute",
            current_code="_ = self_level.nonexistent_attribute",
            suggested_fix="if self_level is None:\n    raise ArchitectureError()",
        )
        aggregator = FindingAggregatorService(mock_reason_factory)
        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=[item1, item2], model_used="test model")
        )

        assert len(review.items) == 1
        assert review.items[0].severity == ItemSeverity.CRITICAL
        assert review.items[0].category == IssueCategory.BUG
        assert review.items[0].line == "42"

    def test_deduplicate_overlapping_lines_keeps_higher_severity(
        self, mock_reason_factory,
    ) -> None:
        item1 = ReviewItem(
            id="item-1",
            severity=ItemSeverity.MINOR,
            category=IssueCategory.STYLE,
            file_path="src/validator.py",
            line="10-15",
            description="Style issue on lines 10-15",
        )
        item2 = ReviewItem(
            id="item-2",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.STYLE,
            file_path="src/validator.py",
            line="12",
            description="Major style violation on line 12",
        )
        aggregator = FindingAggregatorService(mock_reason_factory)
        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=[item1, item2], model_used="test model")
        )

        assert len(review.items) == 1
        assert review.items[0].severity == ItemSeverity.MAJOR

    def test_praise_items_have_empty_suggested_fix(
        self, mock_reason_factory,
    ) -> None:
        mock_reason_factory.make.return_value = "Stub reason"
        phase_result = PhaseResult(
            items=[],
            llm_verdict="approved",
            llm_praise=[
                {
                    "file": "src/validator.py",
                    "description": "Clear error messages and explicit validation.",
                }
            ],
        )
        aggregator = FindingAggregatorService(mock_reason_factory)
        review = aggregator.execute(
            AggregateReviewFindingsCommand(items=[], phase_result=phase_result, model_used="test model")
        )

        assert len(review.praise) == 1
        assert review.praise[0].description == "Clear error messages and explicit validation."
        assert review.praise[0].suggested_fix == ""

    def test_multi_phase_summary_synthesizes_all_blocking_and_categories(
        self, mock_reason_factory,
    ) -> None:
        item1 = ReviewItem(
            id="item-1",
            severity=ItemSeverity.CRITICAL,
            category=IssueCategory.BUG,
            file_path="src/validator.py",
            description="Critical bug in validator",
        )
        item2 = ReviewItem(
            id="item-2",
            severity=ItemSeverity.MINOR,
            category=IssueCategory.MAINTAINABILITY,
            file_path="src/helper.py",
            description="Minor maintainability in helper",
        )
        last_phase = PhaseResult(
            items=[item2],
            llm_summary="Identified 1 non-blocking finding(s) (maintainability) across 1 file(s).",
            llm_reason="Minor maintainability issue.",
        )
        aggregator = FindingAggregatorService(mock_reason_factory)
        review = aggregator.execute(
            AggregateReviewFindingsCommand(
                items=[item1, item2],
                phase_result=last_phase,
                model_used="test model",
            )
        )

        assert len(review.items) == 2
        assert "1 blocking across 2 file(s)" in review.summary
        assert "Files: src/helper.py, src/validator.py" in review.summary
        assert "Identified critical issue" in review.reason
        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED