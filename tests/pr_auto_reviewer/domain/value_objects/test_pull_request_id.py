from dataclasses import FrozenInstanceError

import pytest

from pr_auto_reviewer.domain import InvalidPullRequestIdError, PullRequestId


class TestPullRequestId:
    """Tests for PullRequestId value object."""

    def test_creation(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        assert pr_id.repository == "owner/repo"
        assert pr_id.number == 42

    def test_equality_same_values(self) -> None:
        a = PullRequestId(repository="owner/repo", number=42)
        b = PullRequestId(repository="owner/repo", number=42)
        assert a == b
        assert hash(a) == hash(b)

    def test_equality_different_repository(self) -> None:
        a = PullRequestId(repository="owner/repo", number=42)
        b = PullRequestId(repository="other/repo", number=42)
        assert a != b

    def test_equality_different_number(self) -> None:
        a = PullRequestId(repository="owner/repo", number=42)
        b = PullRequestId(repository="owner/repo", number=99)
        assert a != b

    def test_immutability(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        with pytest.raises(FrozenInstanceError):
            pr_id.number = 99

    def test_str_representation(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        assert str(pr_id) == "owner/repo#42"

    def test_hash_consistency(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        assert hash(pr_id) == hash(pr_id)
        s = {pr_id}
        assert PullRequestId(repository="owner/repo", number=42) in s

    def test_empty_repository_raises(self) -> None:
        with pytest.raises(InvalidPullRequestIdError, match="repository"):
            PullRequestId(repository="", number=1)

    def test_zero_number_raises(self) -> None:
        with pytest.raises(InvalidPullRequestIdError, match="number"):
            PullRequestId(repository="owner/repo", number=0)

    def test_negative_number_raises(self) -> None:
        with pytest.raises(InvalidPullRequestIdError, match="number"):
            PullRequestId(repository="owner/repo", number=-1)
