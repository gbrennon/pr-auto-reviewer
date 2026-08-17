from dataclasses import FrozenInstanceError

import pytest

from pr_auto_reviewer.domain import ItemSeverity, ReviewItem


class TestReviewItem:
    """Tests for ReviewItem value object."""

    def test_creation_with_all_fields(self) -> None:
        item = ReviewItem(
            severity=ItemSeverity.CRITICAL,
            category="security",
            file_path="src/main.py",
            description="SQL injection vulnerability",
            id="test-0001",
        )
        assert item.id == "test-0001"
        assert item.severity == ItemSeverity.CRITICAL
        assert item.category == "security"
        assert item.file_path == "src/main.py"
        assert item.description == "SQL injection vulnerability"

    def test_creation_without_file_path(self) -> None:
        item = ReviewItem(
            severity=ItemSeverity.INFO,
            category="style",
            file_path=None,
            description="Consider adding type hints",
            id="test-0002",
        )
        assert item.file_path is None

    def test_equality_same_fields(self) -> None:
        a = ReviewItem(
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="desc",
            id="a1b2",
        )
        b = ReviewItem(
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="desc",
            id="a1b2",
        )
        assert a == b

    def test_equality_different_number(self) -> None:
        a = ReviewItem(
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="desc",
            id="a1b2",
        )
        b = ReviewItem(
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="desc",
            id="a1b3",
        )
        assert a != b

    def test_equality_different_severity(self) -> None:
        a = ReviewItem(
            severity=ItemSeverity.MAJOR,
            category="bug",
            file_path="x.py",
            description="desc",
            id="a1b2",
        )
        b = ReviewItem(
            severity=ItemSeverity.MINOR,
            category="bug",
            file_path="x.py",
            description="desc",
            id="b1b2",
        )
        assert a != b

    def test_immutability(self) -> None:
        item = ReviewItem(
            severity=ItemSeverity.INFO,
            category="style",
            file_path=None,
            description="desc",
            id="test-immut",
        )
        with pytest.raises(FrozenInstanceError):
            item.description = "changed"

    def test_hash_consistency(self) -> None:
        item = ReviewItem(
            severity=ItemSeverity.CRITICAL,
            category="security",
            file_path="x.py",
            description="desc",
            id="test-hash",
        )
        assert hash(item) == hash(item)
