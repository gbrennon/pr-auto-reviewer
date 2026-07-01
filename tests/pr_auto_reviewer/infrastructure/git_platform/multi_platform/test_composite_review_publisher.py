from unittest.mock import Mock

import pytest

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import ReviewPublisherPort
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_review_publisher import (
    CompositeReviewPublisher,
)


class TestCompositeReviewPublisher:
    def test_publish_routes_to_correct_platform(self):
        codeberg_publisher = Mock(spec=ReviewPublisherPort)
        github_publisher = Mock(spec=ReviewPublisherPort)
        composite = CompositeReviewPublisher({
            "codeberg": codeberg_publisher,
            "github": github_publisher,
        })

        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="test")
        github_pr_id = PullRequestId(repository="github:owner/repo", number=1)
        codeberg_pr_id = PullRequestId(repository="codeberg:org/proj", number=2)

        composite.publish(github_pr_id, review)
        composite.publish(codeberg_pr_id, review)

        github_publisher.publish.assert_called_once_with(github_pr_id, review)
        codeberg_publisher.publish.assert_called_once_with(codeberg_pr_id, review)

    def test_publish_defaults_to_codeberg_without_prefix(self):
        codeberg_publisher = Mock(spec=ReviewPublisherPort)
        composite = CompositeReviewPublisher({
            "codeberg": codeberg_publisher,
        })

        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="test")
        pr_id = PullRequestId(repository="owner/repo", number=1)

        composite.publish(pr_id, review)

        codeberg_publisher.publish.assert_called_once_with(pr_id, review)

    def test_publish_raises_for_unknown_platform(self):
        composite = CompositeReviewPublisher({})

        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="test")
        pr_id = PullRequestId(repository="unknown:owner/repo", number=1)

        with pytest.raises(ValueError, match="No publisher for platform unknown"):
            composite.publish(pr_id, review)
