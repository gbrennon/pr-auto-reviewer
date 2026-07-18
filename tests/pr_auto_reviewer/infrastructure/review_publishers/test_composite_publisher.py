"""Tests for CompositeReviewPublisher using real port implementations."""

import pytest

from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_review_publisher import (
    CompositeReviewPublisher,
)
from tests.fixtures.composite_fixtures import RecordingReviewPublisher


class TestCompositeReviewPublisher:
    def test_publish_routes_to_correct_platform(self):
        forgejo_pub = RecordingReviewPublisher()
        github_pub = RecordingReviewPublisher()
        composite = CompositeReviewPublisher(
            {
                "forgejo": forgejo_pub,
                "github": github_pub,
            }
        )

        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="test")
        github_pr = PullRequestId(repository="github:owner/repo", number=1)
        forgejo_pr = PullRequestId(repository="codeberg:org/proj", number=2)

        composite.publish(github_pr, review)
        composite.publish(forgejo_pr, review)

        assert len(github_pub.publish_calls) == 1
        assert github_pub.publish_calls[0][0].repository == "owner/repo"
        assert len(forgejo_pub.publish_calls) == 1
        assert forgejo_pub.publish_calls[0][0].repository == "org/proj"

    def test_publish_defaults_to_forgejo_without_prefix(self):
        forgejo_pub = RecordingReviewPublisher()
        composite = CompositeReviewPublisher({"forgejo": forgejo_pub})

        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="test")
        pr_id = PullRequestId(repository="owner/repo", number=1)

        composite.publish(pr_id, review)
        assert len(forgejo_pub.publish_calls) == 1

    def test_publish_raises_for_unknown_platform(self):
        composite = CompositeReviewPublisher({})
        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="test")
        pr_id = PullRequestId(repository="gitlab:owner/repo", number=1)

        with pytest.raises(ValueError, match="No publisher for platform"):
            composite.publish(pr_id, review)
