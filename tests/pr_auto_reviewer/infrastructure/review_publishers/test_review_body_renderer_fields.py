"""Tests that ReviewBodyRenderer.render surfaces every field, including nested.

Guards against empty or default-valued fields appearing in the rendered
review body: items, suggestions, and praise must render their real values
and items must be identified by ``id``, never ``number``.
"""

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.entities.review_praise import ReviewPraise
from pr_auto_reviewer.domain.entities.review_suggestion import ReviewSuggestion
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyRenderer,
)
from tests.fakes.fake_review_body_renderer_factory import FakeReviewBodyRendererFactory


_RENDERER = FakeReviewBodyRendererFactory.make()


def _full_review() -> CodeReview:
    return CodeReview(
        verdict=ReviewVerdict.CHANGES_REQUESTED,
        reason="Custom reason",
        summary="Custom summary",
        items=[
            ReviewItem(
                id="i1",
                category=IssueCategory.BUG,
                severity=ItemSeverity.CRITICAL,
                file_path="a/b.py",
                description="item description",
                line="42",
                current_code="broken code",
                suggested_fix="fixed code",
            ),
        ],
        suggestions=[
            ReviewSuggestion(
                id="s1",
                description="suggestion description",
                file="c.py",
                line="9",
                current_code="tmp code",
                suggested_code="clean code",
            ),
        ],
        praise=[ReviewPraise(file="d.py", description="praised design")],
        model_used="model-x",
    )


def _multi_item_review() -> CodeReview:
    return CodeReview(
        verdict=ReviewVerdict.CHANGES_REQUESTED,
        reason="Custom reason",
        summary="Custom summary",
        items=[
            ReviewItem(
                id="i1",
                category=IssueCategory.BUG,
                severity=ItemSeverity.MAJOR,
                file_path="a/b.py",
                description="first item",
                line="3",
                current_code="a",
                suggested_fix="b",
            ),
            ReviewItem(
                id="i2",
                category=IssueCategory.STYLE,
                severity=ItemSeverity.MINOR,
                file_path="c/d.py",
                description="second item",
                line="7",
                current_code="c",
                suggested_fix="d",
            ),
        ],
        suggestions=[],
        praise=[],
        model_used="model-x",
    )


class TestReviewBodyRendererFields:
    """Every render field is populated with its real, non-default value."""

    def test_renders_verdict_reason_and_summary(self) -> None:
        body = _RENDERER.render(_full_review())
        assert "Changes Requested" in body
        assert "Custom reason" in body
        assert "Custom summary" in body

    def test_renders_model_used(self) -> None:
        assert "model-x" in _RENDERER.render(_full_review())

    def test_renders_all_nested_item_fields(self) -> None:
        body = _RENDERER.render(_full_review())
        assert "i1" in body
        assert "BUG" in body or "bug" in body
        assert "CRITICAL" in body
        assert "a/b.py" in body
        assert "42" in body
        assert "item description" in body
        assert "broken code" in body
        assert "fixed code" in body

    def test_renders_all_nested_suggestion_fields(self) -> None:
        body = _RENDERER.render(_full_review())
        assert "s1" in body
        assert "suggestion description" in body
        assert "c.py" in body
        assert "9" in body
        assert "tmp code" in body
        assert "clean code" in body

    def test_renders_all_nested_praise_fields(self) -> None:
        body = _RENDERER.render(_full_review())
        assert "praised design" in body
        assert "d.py" in body

    def test_items_are_identified_by_id_not_number(self) -> None:
        body = _RENDERER.render(_full_review())
        assert "\ni1. [bug] [CRITICAL] a/b.py:42" in body
        assert "number" not in body

    def test_each_item_is_rendered_under_its_own_non_empty_id(self) -> None:
        body = _RENDERER.render(_multi_item_review())
        assert "\ni1. [" in body
        assert "\ni2. [" in body
        assert "\n. [" not in body

    def test_no_default_values_in_rendered_body(self) -> None:
        body = _RENDERER.render(_full_review())
        for default in ("No issues found.", "[]"):
            assert default not in body