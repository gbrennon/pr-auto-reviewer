"""Tests for ReviewBodyRenderer template rendering."""

from pathlib import Path

import pytest

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import ReviewBodyRenderer


class TestReviewBodyRenderer:
    """Tests for ReviewBodyRenderer template rendering."""

    @pytest.fixture
    def renderer(self) -> ReviewBodyRenderer:
        """Create a renderer with the project's template directory.
        
        Test file: tests/pr_auto_reviewer/infrastructure/test_body_formatter.py
        Template: src/pr_auto_reviewer/infrastructure/templates/review_output.j2
        """
        # From test file, go up 3 levels to project root, then into src/
        project_root = Path(__file__).parents[3]
        template_dir = project_root / "src" / "pr_auto_reviewer" / "infrastructure" / "templates"
        return ReviewBodyRenderer(template_dir=template_dir)

    def test_render_includes_item_id(self, renderer: ReviewBodyRenderer) -> None:
        """Item IDs from the domain layer are rendered in the output."""
        item = ReviewItem(
            severity=ItemSeverity.MINOR,
            category=IssueCategory.MAINTAINABILITY,
            file_path="scripts/install.sh",
            description="Fix the typo",
            id="i1a01",
        )
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            items=[item],
            model_used="code-review:latest",
        )
        output = renderer.render(review)
        assert "i1a01." in output, f"Item ID not found in output: {output}"

    def test_render_includes_suggestion_ids(self, renderer: ReviewBodyRenderer) -> None:
        """Suggestion IDs are rendered in the output."""
        suggestions = [
            ReviewItem(
                severity="info",
                category="general",
                file_path="badwolf_gtk/scripts/install.sh",
                description="Fix the typo in the file path",
                line="92-107",
                id="s1",
                current_code="",
                suggested_fix="",
            ),
            ReviewItem(
                severity="info",
                category="general",
                file_path="badwolf_gtk/scripts/install.sh",
                description="Add a check for DEST_THEME_DIR",
                line="92-107",
                id="s2",
                current_code="",
                suggested_fix="",
            ),
        ]
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            suggestions=suggestions,
            model_used="code-review:latest",
        )
        output = renderer.render(review)
        assert "s1." in output, f"Suggestion s1 ID not found in output: {output}"
        assert "s2." in output, f"Suggestion s2 ID not found in output: {output}"

    def test_render_includes_praise_file(self, renderer: ReviewBodyRenderer) -> None:
        """Praise items display their associated file."""
        praise = ReviewItem(
            severity="info",
            category="general",
            file_path="auth.py",
            description="Great function",
            line="",
            id="",
            current_code="",
            suggested_fix="Great function",
        )
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            praise=[praise],
            model_used="code-review:latest",
        )
        output = renderer.render(review)
        assert "- auth.py:" in output, f"Praise file not found in output: {output}"

    def test_render_without_ids_uses_empty_default(self, renderer: ReviewBodyRenderer) -> None:
        """When no IDs are set, the template renders gracefully."""
        suggestion = ReviewItem(
            severity="info",
            category="general",
            file_path="test.py",
            description="No ID set",
            line="10",
        )
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            suggestions=[suggestion],
            model_used="code-review:latest",
        )
        output = renderer.render(review)
        # Should render without crashing; id will be empty string
        assert "Suggestions" in output