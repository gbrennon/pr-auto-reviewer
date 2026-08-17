from dataclasses import FrozenInstanceError

import pytest

from pr_auto_reviewer.domain import CommentId, InvalidCommentIdError


class TestCommentId:
    """Tests for CommentId value object."""

    def test_creation(self) -> None:
        cid = CommentId(value="c_abc123")
        assert cid.value == "c_abc123"

    def test_equality_same(self) -> None:
        a = CommentId(value="c_abc123")
        b = CommentId(value="c_abc123")
        assert a == b
        assert hash(a) == hash(b)

    def test_equality_different(self) -> None:
        a = CommentId(value="c_abc123")
        b = CommentId(value="c_def456")
        assert a != b

    def test_immutability(self) -> None:
        cid = CommentId(value="c_abc123")
        with pytest.raises(FrozenInstanceError):
            cid.value = "changed"

    def test_str_representation(self) -> None:
        cid = CommentId(value="c_abc123")
        assert str(cid) == "c_abc123"

    def test_set_membership(self) -> None:
        a = CommentId(value="c_abc123")
        b = CommentId(value="c_abc123")
        s = {a}
        assert b in s
        assert CommentId(value="c_other") not in s

    def test_empty_value_raises(self) -> None:
        with pytest.raises(InvalidCommentIdError, match="non-empty"):
            CommentId(value="")
