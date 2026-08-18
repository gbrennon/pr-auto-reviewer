"""Tests for ReviewPublisherProcessor.process -> ProcessedReview."""

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.review_publishers._review_processor import (
    ProcessedReview,
    ReviewPublisherProcessor,
)
from pr_auto_reviewer.infrastructure.review_publishers.github_verdict_event_mapper import (
    GithubVerdictEventMapper,
)
from tests.fakes.fake_review_body_renderer_factory import FakeReviewBodyRendererFactory


_BODY = FakeReviewBodyRendererFactory.make()
_PR_ID = PullRequestId(repository="o/r", number=1)


def _processor() -> ReviewPublisherProcessor:
    return ReviewPublisherProcessor(
        _BODY,
        GithubVerdictEventMapper(),
    )


class TestReviewPublisherProcessor:
    """Behaviour of process(pr_id, review) -> ProcessedReview."""

    def test_commented_verdict_uses_comment_path(self) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.COMMENTED,
            reason="",
            summary="no blockers",
            items=[_item(ItemSeverity.MINOR, IssueCategory.STYLE)],
            model_used="m",
        )
        processed = _processor().process(_PR_ID, review)
        assert isinstance(processed, ProcessedReview)
        assert processed.is_comment_only is True
        assert processed.verdict_event == "COMMENT"
        assert processed.blocking_items == []

    def test_approved_verdict_uses_formal_path_with_all_items(self) -> None:
        items = [_item(ItemSeverity.CRITICAL, IssueCategory.SECURITY)]
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="",
            summary="ok",
            items=items,
            model_used="m",
        )
        processed = _processor().process(_PR_ID, review)
        assert processed.is_comment_only is False
        assert processed.verdict_event == "APPROVE"
        assert processed.blocking_items == items

    def test_changes_requested_verdict_maps_request_changes(self) -> None:
        items = [_item(ItemSeverity.MAJOR, IssueCategory.BUG)]
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="",
            summary="needs work",
            items=items,
            model_used="m",
        )
        processed = _processor().process(_PR_ID, review)
        assert processed.verdict_event == "REQUEST_CHANGES"
        assert processed.is_comment_only is False
        assert processed.blocking_items == items

    def test_body_renders_item_id_not_number(self) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="",
            summary="ok",
            items=[_item(ItemSeverity.MAJOR, IssueCategory.BUG)],
            model_used="m",
        )
        processed = _processor().process(_PR_ID, review)
        assert processed.body
        assert "number" not in processed.body


def _item(severity: ItemSeverity, category: IssueCategory) -> ReviewItem:
    return ReviewItem(
        severity=severity,
        category=category,
        file_path="a.py",
        description="a finding",
        id="abcd",
        line="3",
        current_code="x",
        suggested_fix="y",
    )