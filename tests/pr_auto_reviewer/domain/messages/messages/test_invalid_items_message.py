from ._helpers import *


class TestInvalidItemsMessage:
    """Tests for invalid_items_message(invalid, available) -> str."""

    def test_formats_invalid_numbers(self) -> None:
        invalid = [1, 3, 5]
        available: list[ReviewItem] = []
        result = invalid_items_message(invalid, available)
        assert "#1, #3, #5" in result

    def test_formats_available_items(self) -> None:
        invalid: list[int] = []
        available = [
            ReviewItem(id="id-1",
                severity=ItemSeverity.CRITICAL,
                category="security",
                file_path="src/main.py",
                description="SQL injection risk",
            ),
            ReviewItem(id="id-2",
                severity=ItemSeverity.MAJOR,
                category="bug",
                file_path=None,
                description="Off-by-one error",
            ),
        ]
        result = invalid_items_message(invalid, available)
        assert "Available items:" in result
        assert "- #id-1: SQL injection risk..." in result
        assert "- #id-2: Off-by-one error..." in result

    def test_full_message_with_both_invalid_and_available(self) -> None:
        invalid = [4, 5]
        available = [
            ReviewItem(id="id-1",
                severity=ItemSeverity.INFO,
                category="style",
                file_path=None,
                description="Use type hints throughout the module",
            ),
        ]
        result = invalid_items_message(invalid, available)
        assert "Could not find review items: #4, #5." in result
        assert "Available items:" in result
        assert "- #id-1: Use type hints throughout the module..." in result

    def test_description_truncated_at_60_chars(self) -> None:
        invalid: list[int] = []
        long_desc = "X" * 100
        available = [
            ReviewItem(id="id-1",
                severity=ItemSeverity.INFO,
                category="general",
                file_path=None,
                description=long_desc,
            ),
        ]
        result = invalid_items_message(invalid, available)
        expected_desc = long_desc[:60] + "..."
        assert f"- #id-1: {expected_desc}" in result

    def test_single_invalid_item(self) -> None:
        result = invalid_items_message([7], [])
        assert "#7." in result
        assert "#7," not in result

