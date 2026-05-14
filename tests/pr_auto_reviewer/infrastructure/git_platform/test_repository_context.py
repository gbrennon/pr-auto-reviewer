"""Tests for GitRepositoryContextAdapter using fixture data."""

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.git_platform.repository_context import (
    GitRepositoryContextAdapter,
)


class TestGitRepositoryContextAdapter:
    """Tests for GitRepositoryContextAdapter using captured fixture data."""

    def test_fetch_returns_context(self, patched_client):
        """Fetch returns RepositoryContext with architecture hint and structure."""
        adapter = GitRepositoryContextAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        ctx = adapter.fetch(pr_id)
        assert ctx.architecture_hint is not None
        assert ctx.repository_structure is not None
        assert len(ctx.repository_structure) > 0

    def test_fetch_handles_tree_failure(self, patched_client, monkeypatch):
        """Tree fetch failure uses defaults."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: (_ for _ in ()).throw(Exception("Network error")))
        monkeypatch.setattr(patched_client, "get_raw", lambda path: (_ for _ in ()).throw(Exception("Not found")))
        adapter = GitRepositoryContextAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        ctx = adapter.fetch(pr_id)
        assert ctx.architecture_hint == "unknown"
        assert ctx.repository_structure is None
        assert ctx.conventions is None

    def test_fetch_finds_conventions(self, patched_client, monkeypatch):
        """Fetch finds and reads conventions file."""
        def fake_get(path, **kw):
            return {"tree": [{"path": "src/main.py"}]}
        def fake_get_raw(path):
            if "CONVENTIONS.md" in path:
                return "## Conventions\nFollow these."
            raise Exception("Not found")
        monkeypatch.setattr(patched_client, "get", fake_get)
        monkeypatch.setattr(patched_client, "get_raw", fake_get_raw)
        adapter = GitRepositoryContextAdapter(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        ctx = adapter.fetch(pr_id)
        assert ctx.conventions == "## Conventions\nFollow these."
        assert ctx.repository_structure is not None
