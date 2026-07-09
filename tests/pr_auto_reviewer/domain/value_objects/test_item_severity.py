import pytest
from pr_auto_reviewer.domain import ItemSeverity

class TestItemSeverity:
    """Tests for ItemSeverity enum."""

    def test_members_exist(self) -> None:
        assert ItemSeverity.CRITICAL == "critical"
        assert ItemSeverity.MAJOR == "major"
        assert ItemSeverity.MINOR == "minor"
        assert ItemSeverity.INFO == "info"

    def test_four_levels(self) -> None:
        members = list(ItemSeverity)
        assert len(members) == 4
        names = {m.name for m in members}
        assert names == {"CRITICAL", "MAJOR", "MINOR", "INFO"}

    def test_equality(self) -> None:
        assert ItemSeverity.CRITICAL == ItemSeverity.CRITICAL
        assert ItemSeverity.MAJOR != ItemSeverity.MINOR

    def test_str_representation(self) -> None:
        assert str(ItemSeverity.CRITICAL) == "critical"
        assert str(ItemSeverity.MINOR) == "minor"

    def test_hash(self) -> None:
        assert hash(ItemSeverity.CRITICAL) == hash(ItemSeverity.CRITICAL)
        s = {ItemSeverity.CRITICAL, ItemSeverity.INFO}
        assert ItemSeverity.CRITICAL in s

    def test_from_string(self) -> None:
        assert ItemSeverity("critical") == ItemSeverity.CRITICAL
        assert ItemSeverity("major") == ItemSeverity.MAJOR

    def test_from_value_accepts_prompt_aliases(self) -> None:
        assert ItemSeverity.from_value("high") == ItemSeverity.MAJOR
        assert ItemSeverity.from_value("medium") == ItemSeverity.MINOR
        assert ItemSeverity.from_value("low") == ItemSeverity.INFO

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            ItemSeverity("unknown")

    def test_is_blocking_critical(self) -> None:
        assert ItemSeverity.CRITICAL.is_blocking is True

    def test_is_blocking_major(self) -> None:
        assert ItemSeverity.MAJOR.is_blocking is True

    def test_is_blocking_minor(self) -> None:
        assert ItemSeverity.MINOR.is_blocking is False

    def test_is_blocking_info(self) -> None:
        assert ItemSeverity.INFO.is_blocking is False
