"""Tests for ForgejoReviewPublisher publish comment/formal routing."""

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
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
        reason="ok",
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
    def test_publish_mixed_review_splits_formal_and_comment_items(
        self, integration_data: dict, monkeypatch,
    ) -> None:
        post_payloads = []

        def record_post(path, body, *, repo=None):
            post_payloads.append((path, body))
            return {"id": 1}

        reviewer = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
        )
        monkeypatch.setattr(reviewer, "post", record_post)
        owner = SpyClient(
            FixtureHttpClient(integration_data["private"], "private"),
        )
        adapter = ForgejoReviewPublisher(
            body_renderer=_BODY,
            client=reviewer,
            owner_client=owner,
        )
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="Needs changes",
            summary="Mixed findings",
            items=[
                ReviewItem(
                    id="b1",
                    severity=ItemSeverity.MAJOR,
                    category="bug",
                    file_path="src/main.py",
                    description="Blocking finding",
                ),
                ReviewItem(
                    id="n1",
                    severity=ItemSeverity.MINOR,
                    category="style",
                    file_path="src/main.py",
                    description="Non-blocking finding",
                ),
            ],
            suggestions=[
                ReviewItem(
                    id="s1",
                    severity=ItemSeverity.INFO,
                    category="style",
                    file_path="src/main.py",
                    description="Active suggestion",
                ),
            ],
            model_used="m",
        )

        adapter.publish(
            PullRequestId(repository="my-org/my-repo", number=7),
            review,
        )

        review_payloads = [
            body for path, body in post_payloads if "/reviews" in path
        ]
        comment_payloads = [
            body for path, body in post_payloads if "/comments" in path
        ]
        assert len(review_payloads) == 1
        assert len(comment_payloads) == 1
        assert "Blocking finding" in review_payloads[0]["body"]
        assert "Non-blocking finding" not in review_payloads[0]["body"]
        assert "Active suggestion" not in review_payloads[0]["body"]
        assert "Non-blocking finding" in comment_payloads[0]["body"]
        assert "Active suggestion" in comment_payloads[0]["body"]

