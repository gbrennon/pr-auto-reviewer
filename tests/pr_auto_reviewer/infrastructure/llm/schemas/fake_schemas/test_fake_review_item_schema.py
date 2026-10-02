from ._helpers import *


class TestFakeReviewItemSchema:
    """Tests using the fake review item schema."""

    def test_fake_schema_defaults(self) -> None:
        """Fake schema has default values."""
        fake = FakeReviewItemSchema()
        assert fake.file == ""
        assert fake.severity == "info"
        assert fake.category == "maintainability"

    def test_fake_schema_custom_values(self) -> None:
        """Fake schema can be customized."""
        fake = FakeReviewItemSchema(
            file="test.py",
            severity="critical",
            category="security",
            description="Test issue",
            line="10",
            current_code="old code",
            suggested_fix="new code",
        )
        assert fake.file == "test.py"
        assert fake.severity == "critical"
        assert fake.category == "security"

    def test_fake_schema_from_parser_dict(self) -> None:
        """Fake schema can be constructed from parser dict."""
        data: dict[str, object] = {
            "file": "test.py", "severity": "major", "description": "issue"
        }
        fake = FakeReviewItemSchema.from_parser_dict(data)
        assert fake.file == "test.py"
        assert fake.severity == "major"

    def test_fake_schema_model_dump(self) -> None:
        """Fake schema model_dump returns dict."""
        fake = FakeReviewItemSchema(file="test.py", severity="critical")
        d = fake.model_dump()
        assert d["file"] == "test.py"
        assert d["severity"] == "critical"

