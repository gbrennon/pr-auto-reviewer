from pathlib import Path

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_item_status import ReviewItemStatus
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.review_publishers.forgejo_verdict_event_mapper import (
    ForgejoVerdictEventMapper,
)
from pr_auto_reviewer.infrastructure.review_publishers._review_processor import (
    ReviewPublisherProcessor,
)
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyRenderer,
)


_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "pr_auto_reviewer"
    / "infrastructure"
    / "templates"
)


def test_publisher_body_excludes_dismissed_suggestion() -> None:
    suggestion = ReviewItem(
        id="suggestion-1",
        severity=ItemSeverity.INFO,
        category=IssueCategory.GENERAL,
        file_path="src/example.py",
        description="Prefer a named helper.",
        status=ReviewItemStatus.DISMISSED,
    )
    review = CodeReview(
        verdict=ReviewVerdict.APPROVED,
        reason="No blocking issues remain.",
        summary="The review contains one dismissed suggestion.",
        suggestions=[suggestion],
        model_used="integration-test",
    )
    processor = ReviewPublisherProcessor(
        ReviewBodyRenderer(_TEMPLATE_DIR),
        ForgejoVerdictEventMapper(),
    )

    processed = processor.process(
        PullRequestId(repository="forgejo:owner/repo", number=4),
        review,
    )

    assert "`suggestion-1`. [DISMISSED] src/example.py" not in processed.body
    assert processed.comment_body is None
    assert processed.verdict_event == "APPROVED"
    assert processed.blocking_items == []
