import pytest
from pr_auto_reviewer.core.models import CommitSha, InvalidCommitShaError


class TestCommitSha:
    """Tests for CommitSha value object."""

    def test_creation_full_sha(self) -> None:
        sha = CommitSha(value="abc123def456789012345678901234567890abcd")
        assert sha.value == "abc123def456789012345678901234567890abcd"

    def test_creation_abbreviated_sha(self) -> None:
        sha = CommitSha(value="abc123d")
        assert sha.value == "abc123d"

    def test_empty_value_raises(self) -> None:
        with pytest.raises(InvalidCommitShaError, match="non-empty"):
            CommitSha(value="")

    def test_equality_same_sha(self) -> None:
        a = CommitSha(value="abc123")
        b = CommitSha(value="abc123")
        assert a == b
        assert hash(a) == hash(b)

    def test_equality_different_sha(self) -> None:
        a = CommitSha(value="abc123")
        b = CommitSha(value="def456")
        assert a != b

    def test_immutability(self) -> None:
        sha = CommitSha(value="abc123")
        with pytest.raises(Exception):
            sha.value = "def456"  # type: ignore[misc]

    def test_str_representation(self) -> None:
        sha = CommitSha(value="abc123def")
        assert str(sha) == "abc123def"

    def test_set_membership(self) -> None:
        a = CommitSha(value="abc123")
        b = CommitSha(value="abc123")
        s = {a}
        assert b in s
