from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from tests.fakes.fake_forgejo_review_publisher import FakeForgejoReviewPublisher


class TestFakeForgejoReviewPublisher:
    """Tests using the fake ForgejoReviewPublisher."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake review publisher can be instantiated."""
        fake = FakeForgejoReviewPublisher()
        assert fake is not None

    def test_fake_publish(self) -> None:
        """Fake publish tracks calls without making HTTP call."""
        fake = FakeForgejoReviewPublisher()

        # Create a minimal CodeReview for testing
        review = CodeReview(
            verdict="approved",
            reason="test reason",
            summary="test summary",
            model_used="test model",
        )

        result = fake.publish(review, official=True)

        assert len(fake.publish_calls) == 1
        verdict, _published_review, official = fake.publish_calls[0]
        assert verdict == "approved"
        assert official is True
        assert result == "approved_event"