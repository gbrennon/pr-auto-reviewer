"""Behavioral tests for GithubCommentReader."""

from datetime import UTC, datetime

import pytest

from pr_auto_reviewer.domain.exceptions.invalid_comment_id_error import (
    InvalidCommentIdError,
)
from pr_auto_reviewer.domain.value_objects.comment_id import CommentId
from pr_auto_reviewer.domain.value_objects.pr_comment import PrComment
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.github.comment_reader import (
    GithubCommentReader,
)
from tests.fakes import FakeGitPlatformHttpClient


def _reader(paths: dict) -> GithubCommentReader:
    return GithubCommentReader(FakeGitPlatformHttpClient(paths))


PR = PullRequestId(repository="o/r", number=3)
PATH = "/repos/o/r/issues/3/comments"
COMMENT = {"id": "1", "body": "review body", "created_at": "2024-01-01T00:00:00+00:00"}


class TestGithubCommentReader:
    """Exercises GithubCommentReader response-shape handling."""

    def test_get_comments_when_list_then_maps_to_pr_comments(self) -> None:
        """A list response produces one PrComment per entry."""
        result = _reader({PATH: [COMMENT]}).get_comments(PR)

        assert len(result) == 1
        assert isinstance(result[0], PrComment)
        assert result[0].id == CommentId("1")
        assert result[0].body == "review body"

    def test_get_comments_when_dict_data_key_then_unwraps(self) -> None:
        """A {data: [...]} response is unwrapped."""
        result = _reader({PATH: {"data": [dict(COMMENT, id="2")]}}).get_comments(PR)

        assert [c.body for c in result] == ["review body"]

    def test_get_comments_when_dict_comments_key_then_unwraps(self) -> None:
        """A {comments: [...]} response is unwrapped."""
        result = _reader({PATH: {"comments": [dict(COMMENT, id="3")]}}).get_comments(PR)

        assert [c.body for c in result] == ["review body"]

    def test_get_comments_when_plain_dict_then_returns_empty(self) -> None:
        """A dict without data/comments keys yields no comments."""
        assert _reader({PATH: {"unrelated": True}}).get_comments(PR) == []

    def test_get_comments_when_scalar_response_then_returns_empty(self) -> None:
        """A non-list non-dict response yields no comments."""
        assert _reader({PATH: "just text"}).get_comments(PR) == []

    def test_get_comments_when_data_key_non_list_then_raises_on_empty_id(self) -> None:
        """A wrapped entry without an id violates the CommentId invariant."""
        reader = _reader({PATH: {"data": "x"}})

        with pytest.raises(InvalidCommentIdError):
            reader.get_comments(PR)

    def test_get_comments_when_entry_missing_id_then_raises(self) -> None:
        """An entry with no id is rejected by CommentId."""
        reader = _reader({PATH: [{"body": "no id", "created_at": "2024-01-01T00:00:00+00:00"}]})

        with pytest.raises(InvalidCommentIdError):
            reader.get_comments(PR)

    def test_get_comments_when_missing_created_at_then_uses_epoch(self) -> None:
        """A missing created_at falls back to the epoch."""
        result = _reader({PATH: [{"id": "1", "body": "x"}]}).get_comments(PR)

        assert result[0].created_at == datetime.min.replace(tzinfo=UTC)

    def test_get_comments_when_invalid_created_at_then_uses_epoch(self) -> None:
        """An unparseable created_at falls back to the epoch."""
        result = _reader({PATH: [{"id": "1", "body": "x", "created_at": "nope"}]}).get_comments(PR)

        assert result[0].created_at == datetime.min.replace(tzinfo=UTC)

    def test_get_comments_when_unsorted_then_sorts_ascending(self) -> None:
        """Comments come back ordered by creation time ascending."""
        result = _reader(
            {
                PATH: [
                    dict(COMMENT, id="2", created_at="2024-01-02T00:00:00+00:00"),
                    dict(COMMENT, id="1", created_at="2024-01-01T00:00:00+00:00"),
                ]
            }
        ).get_comments(PR)

        assert [c.id.value for c in result] == ["1", "2"]