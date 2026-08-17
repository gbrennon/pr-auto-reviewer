"""Tests for CompositeReviewPublisher with stub publishers."""

import pytest

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_review_publisher import (
    CompositeReviewPublisher,
)


class _StubReviewPublisher(ReviewPublisherPort):
    """Stub publisher that records calls for test assertion."""

    def __init__(self) -> None:
        self.calls: list[tuple[PullRequestId, CodeReview, PullRequestDiff | None]] = []

    def publish(self, pr_id: PullRequestId, review: CodeReview, diff: PullRequestDiff | None = None) -> None:
        self.calls.append((pr_id, review, diff))


class TestCompositeReviewPublisher:
    def test_publish_routes_to_correct_platform(self):
        codeberg_publisher = _StubReviewPublisher()
        github_publisher = _StubReviewPublisher()
        composite = CompositeReviewPublisher({
            "forgejo": codeberg_publisher,
            "github": github_publisher,
        })

        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="test")
        github_pr_id = PullRequestId(repository="github:owner/repo", number=1)
        codeberg_pr_id = PullRequestId(repository="codeberg:org/proj", number=2)

        composite.publish(github_pr_id, review)
        composite.publish(codeberg_pr_id, review)

        assert len(github_publisher.calls) == 1
        assert github_publisher.calls[0] == (
            PullRequestId(repository="owner/repo", number=1), review, None
        )
        assert len(codeberg_publisher.calls) == 1
        assert codeberg_publisher.calls[0] == (
            PullRequestId(repository="org/proj", number=2), review, None
        )

    def test_publish_defaults_to_forgejo_without_prefix(self):
        codeberg_publisher = _StubReviewPublisher()
        composite = CompositeReviewPublisher({
            "forgejo": codeberg_publisher,
        })

        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="test")
        pr_id = PullRequestId(repository="owner/repo", number=1)

        composite.publish(pr_id, review)

        assert len(codeberg_publisher.calls) == 1
        assert codeberg_publisher.calls[0] == (pr_id, review, None)

    def test_publish_raises_for_unknown_platform(self):
        composite = CompositeReviewPublisher({})

        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="test")
        pr_id = PullRequestId(repository="unknown:owner/repo", number=1)

        with pytest.raises(ValueError, match="No publisher for platform unknown"):
            composite.publish(pr_id, review)
