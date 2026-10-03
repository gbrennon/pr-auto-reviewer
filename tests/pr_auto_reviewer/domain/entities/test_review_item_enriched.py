"""Tests for ReviewItem remediation-context fields."""

from __future__ import annotations

from pr_auto_reviewer.domain.entities.review_item import ReviewItem


class TestReviewItemEnrichedFields:
    """The four fields that make remediation provable and auditable."""

    def test_carries_remediation_context(self) -> None:
        item = ReviewItem(
            severity="critical",
            category="security",
            file_path="src/a.py",
            description="SQL injection in query builder",
            root_cause="user input concatenated into SQL",
            reproduction="call build_query(\"' OR 1=1\")",
            acceptance_criteria="parameterized query; injection input returns no rows",
            detection_method="trace tainted input to the SQL sink",
        )
        assert item.root_cause == "user input concatenated into SQL"
        assert item.reproduction == "call build_query(\"' OR 1=1\")"
        assert item.acceptance_criteria.startswith("parameterized")
        assert item.detection_method == "trace tainted input to the SQL sink"

    def test_fields_default_to_empty_for_back_compat(self) -> None:
        item = ReviewItem(
            severity="minor",
            category="general",
            file_path="src/a.py",
            description="x",
        )
        assert item.root_cause == ""
        assert item.reproduction == ""
        assert item.acceptance_criteria == ""
        assert item.detection_method == ""
