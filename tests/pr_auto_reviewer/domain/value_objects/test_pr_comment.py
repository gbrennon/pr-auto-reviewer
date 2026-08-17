"""Tests for PrComment value object."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from pr_auto_reviewer.domain import CommentId, PrComment


class TestPrComment:
    """Tests for PrComment frozen dataclass."""

    def test_creation_with_all_fields(self) -> None:
        cid = CommentId(value="c_abc123")
        created = datetime(2025, 1, 15, 12, 30, 0, tzinfo=UTC)
        comment = PrComment(id=cid, body="Looks good", created_at=created)
        assert comment.id == cid
        assert comment.body == "Looks good"
        assert comment.created_at == created

    def test_equality_same_fields(self) -> None:
        cid = CommentId(value="c_abc123")
        created = datetime(2025, 1, 15, 12, 30, 0, tzinfo=UTC)
        a = PrComment(id=cid, body="Body", created_at=created)
        b = PrComment(id=cid, body="Body", created_at=created)
        assert a == b

    def test_equality_different_id(self) -> None:
        created = datetime(2025, 1, 15, 12, 30, 0, tzinfo=UTC)
        a = PrComment(id=CommentId(value="c_one"), body="X", created_at=created)
        b = PrComment(id=CommentId(value="c_two"), body="X", created_at=created)
        assert a != b

    def test_equality_different_body(self) -> None:
        cid = CommentId(value="c_abc123")
        created = datetime(2025, 1, 15, 12, 30, 0, tzinfo=UTC)
        a = PrComment(id=cid, body="A", created_at=created)
        b = PrComment(id=cid, body="B", created_at=created)
        assert a != b

    def test_equality_different_created_at(self) -> None:
        cid = CommentId(value="c_abc123")
        a = PrComment(
            id=cid,
            body="Body",
            created_at=datetime(2025, 1, 15, tzinfo=UTC),
        )
        b = PrComment(
            id=cid,
            body="Body",
            created_at=datetime(2025, 2, 20, tzinfo=UTC),
        )
        assert a != b

    def test_immutability(self) -> None:
        cid = CommentId(value="c_abc123")
        created = datetime(2025, 1, 15, tzinfo=UTC)
        comment = PrComment(id=cid, body="Body", created_at=created)
        with pytest.raises(FrozenInstanceError):
            comment.body = "changed"

    def test_hash_consistency(self) -> None:
        cid = CommentId(value="c_abc123")
        created = datetime(2025, 1, 15, tzinfo=UTC)
        comment = PrComment(id=cid, body="Body", created_at=created)
        assert hash(comment) == hash(comment)

    def test_set_membership(self) -> None:
        cid = CommentId(value="c_abc123")
        created = datetime(2025, 1, 15, tzinfo=UTC)
        a = PrComment(id=cid, body="Body", created_at=created)
        b = PrComment(id=cid, body="Body", created_at=created)
        s = {a}
        assert b in s
        other = PrComment(
            id=CommentId(value="c_other"),
            body="Body",
            created_at=created,
        )
        assert other not in s

    def test_str_representation(self) -> None:
        cid = CommentId(value="c_abc123")
        created = datetime(2025, 1, 15, 12, 30, 0, tzinfo=UTC)
        comment = PrComment(id=cid, body="Body", created_at=created)
        text = str(comment)
        assert "c_abc123" in text
        assert "Body" in text

    def test_empty_body(self) -> None:
        cid = CommentId(value="c_abc123")
        created = datetime(2025, 1, 15, tzinfo=UTC)
        comment = PrComment(id=cid, body="", created_at=created)
        assert comment.body == ""
