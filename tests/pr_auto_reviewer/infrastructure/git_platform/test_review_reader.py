"""Tests for ForgejoReviewReader using fixture data."""

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.forgejo.review_reader import (
    ForgejoReviewReader,
)


class TestForgejoReviewReader:
    """Tests for ForgejoReviewReader using captured fixture data."""

    def test_get_latest_review(self, patched_client):
        """Get latest review returns a body string or None."""
        adapter = ForgejoReviewReader(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        body = adapter.get_latest_review(pr_id)
        assert body is None or isinstance(body, str)

    def test_get_latest_review_empty_list(self, patched_client, monkeypatch):
        """Returns None when reviews list is empty."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: [])
        adapter = ForgejoReviewReader(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        assert adapter.get_latest_review(pr_id) is None

    def test_get_latest_review_dict_response(self, patched_client, monkeypatch):
        """Handles single dict response."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: {"body": "lgtm"})
        adapter = ForgejoReviewReader(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        assert adapter.get_latest_review(pr_id) == "lgtm"

    def test_get_latest_review_picks_most_recent(self, patched_client, monkeypatch):
        """Picks review with most recent submitted_at."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: [
            {"submitted_at": "2024-01-01T00:00:00Z", "body": "old"},
            {"submitted_at": "2024-06-01T00:00:00Z", "body": "new"},
        ])
        adapter = ForgejoReviewReader(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        assert adapter.get_latest_review(pr_id) == "new"

    def test_get_latest_review_empty_dict(self, patched_client, monkeypatch):
        """Handles empty dict response."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: {})
        adapter = ForgejoReviewReader(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        assert adapter.get_latest_review(pr_id) is None
