from ._helpers import *


class TestFakeReviewItem:
    """Tests using the fake review item."""

    def test_fake_item_defaults(self) -> None:
        """Fake item has default values."""
        fake = FakeReviewItem()
        assert fake.file == ""
        assert fake.severity == "info"

    def test_fake_item_custom_values(self) -> None:
        """Fake item can be customized."""
        fake = FakeReviewItem(
            file="test.py",
            severity="major",
            description="Test issue",
        )
        assert fake.file == "test.py"
        assert fake.severity == "major"
