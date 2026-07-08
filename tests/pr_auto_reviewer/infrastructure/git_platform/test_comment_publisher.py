"""Tests for ForgejoCommentPublisher using fixture data."""

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.forgejo.comment_publisher import (
    ForgejoCommentPublisher,
)

class TestForgejoCommentPublisher:
    """Tests for ForgejoCommentPublisher using captured fixture data."""

    def test_post_succeeds(self, patched_private_client):
        """Post sends comment without error."""
        adapter = ForgejoCommentPublisher(patched_private_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.post(pr_id, "test comment")

    def test_post_non_fatal_on_error(self, patched_private_client, monkeypatch):
        """POST failure is logged but not raised."""
        monkeypatch.setattr(
            patched_private_client, "post",
            lambda path, body: (_ for _ in ()).throw(Exception("Network error"))
        )
        adapter = ForgejoCommentPublisher(patched_private_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.post(pr_id, "test")
