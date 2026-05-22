"""Tests for GitCommentReaderAdapter using fixture data."""

import pytest

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.exceptions.invalid_comment_id_error import (
    InvalidCommentIdError,
)
from pr_auto_reviewer.infrastructure.git_platform.comment_reader import (
    GitCommentReaderAdapter,
)


class TestGitCommentReaderAdapter:
    """Tests for GitCommentReaderAdapter using captured fixture data."""

    def test_get_comments_returns_list(self, patched_client):
        """Get comments returns a list of PrComment objects."""
        adapter = GitCommentReaderAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        comments = adapter.get_comments(pr_id)
        assert isinstance(comments, list)

    def test_get_comments_dict_with_data_key(self, patched_client, monkeypatch):
        """Handles response wrapped in {data: [...]}."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: {
            "data": [{"id": 1, "body": "c1", "created_at": "2024-01-01T00:00:00Z"}]
        })
        adapter = GitCommentReaderAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        comments = adapter.get_comments(pr_id)
        assert len(comments) == 1
        assert comments[0].body == "c1"

    def test_get_comments_dict_with_comments_key(self, patched_client, monkeypatch):
        """Handles response wrapped in {comments: [...]}."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: {
            "comments": [{"id": 2, "body": "c2", "created_at": "2024-01-02T00:00:00Z"}]
        })
        adapter = GitCommentReaderAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        comments = adapter.get_comments(pr_id)
        assert len(comments) == 1
        assert comments[0].body == "c2"

    def test_get_comments_plain_dict(self, patched_client, monkeypatch):
        """Plain dict without data/comments key returns empty list."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: {
            "id": 3, "body": "c3", "created_at": "2024-01-03T00:00:00Z"
        })
        adapter = GitCommentReaderAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        comments = adapter.get_comments(pr_id)
        assert comments == []

    def test_get_comments_non_list_non_dict(self, patched_client, monkeypatch):
        """Handles response that is neither list nor dict."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: None)
        adapter = GitCommentReaderAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        comments = adapter.get_comments(pr_id)
        assert comments == []

    def test_get_comments_data_key_non_list(self, patched_client, monkeypatch):
        """Handles data key whose value is not a list (line 39)."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: {
            "data": "not-a-list"
        })
        adapter = GitCommentReaderAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        with pytest.raises(InvalidCommentIdError):
            adapter.get_comments(pr_id)

    def test_get_comments_empty_dict(self, patched_client, monkeypatch):
        """Handles empty dict response."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: {})
        adapter = GitCommentReaderAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        comments = adapter.get_comments(pr_id)
        assert comments == []

    def test_get_comments_missing_created_at(self, patched_client, monkeypatch):
        """Handles missing created_at gracefully."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: [
            {"id": 4, "body": "no date"}
        ])
        adapter = GitCommentReaderAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        comments = adapter.get_comments(pr_id)
        assert len(comments) == 1

    def test_get_comments_missing_id(self, patched_client, monkeypatch):
        """Missing id causes InvalidCommentIdError."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: [
            {"body": "no id", "created_at": "2024-01-01T00:00:00Z"}
        ])
        adapter = GitCommentReaderAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        with pytest.raises(InvalidCommentIdError):
            adapter.get_comments(pr_id)

    def test_get_comments_sorts_by_created_at(self, patched_client, monkeypatch):
        """Comments sorted by created_at ascending."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: [
            {"id": 1, "body": "newer", "created_at": "2024-01-02T00:00:00Z"},
            {"id": 2, "body": "older", "created_at": "2024-01-01T00:00:00Z"},
        ])
        adapter = GitCommentReaderAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        comments = adapter.get_comments(pr_id)
        assert comments[0].body == "older"
        assert comments[1].body == "newer"
