from dataclasses import FrozenInstanceError

import pytest

from pr_auto_reviewer.domain import IssueCommand


class TestIssueCommand:
    """Tests for IssueCommand value object."""

    def test_creation_with_items(self) -> None:
        cmd = IssueCommand(comment_id="12345", item_numbers=[1, 2, 3])
        assert cmd.comment_id == "12345"
        assert cmd.item_numbers == [1, 2, 3]

    def test_creation_empty_items(self) -> None:
        cmd = IssueCommand(comment_id="12345")
        assert cmd.item_numbers == []

    def test_equality_same(self) -> None:
        a = IssueCommand(comment_id="12345", item_numbers=[1, 2])
        b = IssueCommand(comment_id="12345", item_numbers=[1, 2])
        assert a == b

    def test_equality_different_comment_id(self) -> None:
        a = IssueCommand(comment_id="12345", item_numbers=[1])
        b = IssueCommand(comment_id="67890", item_numbers=[1])
        assert a != b

    def test_equality_different_items(self) -> None:
        a = IssueCommand(comment_id="12345", item_numbers=[1])
        b = IssueCommand(comment_id="12345", item_numbers=[2])
        assert a != b

    def test_immutability(self) -> None:
        cmd = IssueCommand(comment_id="12345", item_numbers=[1])
        with pytest.raises(FrozenInstanceError):
            cmd.item_numbers = [2]

    def test_hash_consistency(self) -> None:
        cmd = IssueCommand(comment_id="12345", item_numbers=[1])
        with pytest.raises(TypeError, match="unhashable"):
            hash(cmd)
