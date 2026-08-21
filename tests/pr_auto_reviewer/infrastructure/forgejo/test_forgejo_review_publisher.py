"""Tests for ForgejoReviewPublisher publish comment/formal routing."""

from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.forgejo.forgejo_review_publisher import (
    ForgejoReviewPublisher,
)
from tests.fakes import SpyClient
from tests.fakes.fake_review_body_renderer_factory import FakeReviewBodyRendererFactory
from tests.fixtures.integration_fixtures import FixtureHttpClient


_BODY = FakeReviewBodyRendererFactory.make()


def _review(verdict: ReviewVerdict) -> CodeReview:
    return CodeReview(
        verdict=verdict,
        reason="",
        summary="ok",
        items=[],
        model_used="m",
    )


class TestForgejoReviewPublisher:
    """Behaviour of ForgejoReviewPublisher.publish for non-COMMENT verdicts."""

    def test_publish_approved_review_posts_formal_review(
        self, integration_data: dict,
    ) -> None:
        reviewer = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
        )
        owner = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
        )
        adapter = ForgejoReviewPublisher(
            body_renderer=_BODY,
            client=reviewer,
            owner_client=owner,
        )
        pr_id = PullRequestId(repository="my-org/my-repo", number=7)

        adapter.publish(pr_id, _review(ReviewVerdict.APPROVED))

        assert reviewer.verify_calls == [pr_id]
        assert any("/reviews" in path for path, _ in reviewer.post_calls)

    def test_publish_commented_review_uses_comment_path(
        self, integration_data: dict,
    ) -> None:
        reviewer = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
        )
        owner = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
        )
        adapter = ForgejoReviewPublisher(
            body_renderer=_BODY,
            client=reviewer,
            owner_client=owner,
        )
        pr_id = PullRequestId(repository="my-org/my-repo", number=9)

        adapter.publish(pr_id, _review(ReviewVerdict.COMMENTED))

        assert reviewer.verify_calls == [pr_id]
        assert not any("/reviews" in path for path, _ in reviewer.post_calls)
        assert any("/comments" in path for path, _ in reviewer.post_calls)