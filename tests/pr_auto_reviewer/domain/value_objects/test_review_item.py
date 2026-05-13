import pytest
from pr_auto_reviewer.domain import ReviewItem, ItemSeverity


class TestReviewItem:
    """Tests for ReviewItem value object."""

    def test_creation_with_all_fields(self) -> None:
        item = ReviewItem(
            number=1,
            severity=ItemSeverity.CRITICAL,
            category="security",
            file_path="src/main.py",
            description="SQL injection vulnerability",
        )
        assert item.number == 1
        assert item.severity == ItemSeverity.CRITICAL
        assert item.category == "security"
        assert item.file_path == "src/main.py"
        assert item.description == "SQL injection vulnerability"

    def test_creation_without_file_path(self) -> None:
        item = ReviewItem(
            number=2,
            severity=ItemSeverity.INFO,
            category="style",
            file_path=None,
            description="Consider adding type hints",
        )
        assert item.file_path is None

    def test_equality_same_fields(self) -> None:
        a = ReviewItem(
            number=1,
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="desc",
        )
        b = ReviewItem(
            number=1,
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="desc",
        )
        assert a == b

    def test_equality_different_number(self) -> None:
        a = ReviewItem(
            number=1,
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="desc",
        )
        b = ReviewItem(
            number=2,
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="desc",
        )
        assert a != b

    def test_equality_different_severity(self) -> None:
        a = ReviewItem(
            number=1,
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="desc",
        )
        b = ReviewItem(
            number=1,
            severity=ItemSeverity.MINOR,
            category="bug",
            file_path="x.py",
            description="desc",
        )
        assert a != b

    def test_immutability(self) -> None:
        item = ReviewItem(
            number=1,
            severity=ItemSeverity.INFO,
            category="style",
            file_path=None,
            description="desc",
        )
        with pytest.raises(Exception):
            item.description = "changed"  # type: ignore[misc]

    def test_hash_consistency(self) -> None:
        item = ReviewItem(
            number=1,
            severity=ItemSeverity.CRITICAL,
            category="security",
            file_path="x.py",
            description="desc",
        )
        assert hash(item) == hash(item)
