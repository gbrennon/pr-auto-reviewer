"""Tests for GithubReviewPublisher._verify_tokens preflight flow."""

from __future__ import annotations

import pytest

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.exceptions.preflight_verification_error import (
    PreflightVerificationError,
)
from pr_auto_reviewer.domain.exceptions.review_publish_error import (
    ReviewPublishError,
)
from pr_auto_reviewer.infrastructure.github.github_review_publisher import (
    GithubReviewPublisher,
)
from tests.fixtures.integration_fixtures import FixtureHttpClient, integration_data

from tests.fakes.publisher_fakes import SpyClient


def _build_review(verdict: ReviewVerdict = ReviewVerdict.APPROVED) -> CodeReview:
    return CodeReview(
        verdict=verdict,
        reason="LGTM",
        summary="All good",
        items=[
            ReviewItem(
                number=1,
                severity=ItemSeverity.MINOR,
                category=IssueCategory.STYLE,
                file_path="src/foo.py",
                description="Minor style issue",
            ),
        ],
        model_used="test-model",
    )


def _preflight_error() -> PreflightVerificationError:
    return PreflightVerificationError(
        platform="forgejo",
        org="test-org",
        role="reviewer",
        http_status=403,
        step="write_access",
        url="https://codeberg.org/api/v1/repos/test-org/repo/pulls/1/requested_reviewers",
        method="POST",
    )


class TestPublisherVerifyTokens:
    def test_verify_tokens_called_during_publish(
        self, integration_data: dict,
    ) -> None:
        reviewer_spy = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
        )
        owner_spy = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
        )
        adapter = GithubReviewPublisher(
            client=reviewer_spy,
            reviewer_username="reviewer-bot",
            owner_client=owner_spy,
        )

        pr_id = PullRequestId(repository="my-org/my-repo", number=1)
        review = _build_review(ReviewVerdict.APPROVED)

        adapter.publish(pr_id, review)

        assert len(reviewer_spy.verify_calls) == 1
        assert reviewer_spy.verify_calls[0] == pr_id
        assert len(owner_spy.verify_calls) == 1
        assert owner_spy.verify_calls[0] == pr_id

    def test_verify_tokens_reviewer_failure_wraps_as_review_publish_error(
        self, integration_data: dict,
    ) -> None:
        reviewer_spy = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
            fail_verify=_preflight_error(),
        )
        owner_spy = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
        )
        adapter = GithubReviewPublisher(
            client=reviewer_spy,
            reviewer_username="reviewer-bot",
            owner_client=owner_spy,
        )
        pr_id = PullRequestId(repository="my-org/my-repo", number=42)
        review = _build_review()

        with pytest.raises(ReviewPublishError, match="my-org/my-repo#42"):
            adapter.publish(pr_id, review)

        assert len(reviewer_spy.verify_calls) == 1
        assert len(owner_spy.verify_calls) == 0

    def test_verify_tokens_owner_failure_wraps_as_review_publish_error(
        self, integration_data: dict,
    ) -> None:
        reviewer_spy = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
        )
        owner_spy = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
            fail_verify=_preflight_error(),
        )
        adapter = GithubReviewPublisher(
            client=reviewer_spy,
            reviewer_username="reviewer-bot",
            owner_client=owner_spy,
        )
        pr_id = PullRequestId(repository="my-org/my-repo", number=7)
        review = _build_review()

        with pytest.raises(ReviewPublishError, match="my-org/my-repo#7"):
            adapter.publish(pr_id, review)

        assert len(reviewer_spy.verify_calls) == 1
        assert len(owner_spy.verify_calls) == 1

    def test_verify_tokens_non_fatal_other_exceptions_propagate(
        self, integration_data: dict,
    ) -> None:
        """A non-PreflightVerificationError is NOT caught by _verify_tokens."""
        reviewer_spy = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
            fail_verify=ValueError("msg"),
        )
        owner_spy = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
        )
        adapter = GithubReviewPublisher(
            client=reviewer_spy,
            reviewer_username="reviewer-bot",
            owner_client=owner_spy,
        )

        pr_id = PullRequestId(repository="my-org/my-repo", number=1)
        review = _build_review()

        with pytest.raises(ValueError, match="msg"):
            adapter.publish(pr_id, review)
