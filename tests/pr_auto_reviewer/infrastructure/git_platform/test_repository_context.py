"""Tests for ForgejoRepositoryContext using fixture data."""

import logging

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.forgejo.repository_context import (
    ForgejoRepositoryContext,
)

class TestForgejoRepositoryContext:
    """Tests for ForgejoRepositoryContext using captured fixture data."""

    def test_fetch_returns_context(self, patched_client):
        """Fetch returns RepositoryContext with architecture hint and structure."""
        adapter = ForgejoRepositoryContext(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        ctx = adapter.fetch(pr_id)
        assert ctx.architecture_hint is not None
        assert ctx.repository_structure is not None
        assert len(ctx.repository_structure) > 0

    def test_fetch_handles_tree_failure(self, patched_client, monkeypatch):
        """Tree fetch failure uses defaults."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: (_ for _ in ()).throw(Exception("Network error")))
        monkeypatch.setattr(patched_client, "get_raw", lambda path, *, repo=None: (_ for _ in ()).throw(Exception("Not found")))
        adapter = ForgejoRepositoryContext(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        ctx = adapter.fetch(pr_id)
        assert ctx.architecture_hint == "unknown"
        assert ctx.repository_structure is None
        assert ctx.conventions is None

    def test_fetch_finds_conventions(self, patched_client, monkeypatch):
        """Fetch finds and reads conventions file."""
        def fake_get(path, **kw):
            return {"tree": [{"path": "src/main.py"}, {"path": "CONVENTIONS.md"}]}
        def fake_get_raw(path, *, repo=None):
            if "CONVENTIONS.md" in path:
                return "## Conventions\nFollow these."
            raise Exception("Not found")
        monkeypatch.setattr(patched_client, "get", fake_get)
        monkeypatch.setattr(patched_client, "get_raw", fake_get_raw)
        adapter = ForgejoRepositoryContext(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        ctx = adapter.fetch(pr_id)
        assert ctx.conventions == "## Conventions\nFollow these."

    def test_fetch_uses_target_branch_for_tree_url(self, patched_client, monkeypatch):
        """When target_branch='dev', git tree URL uses /trees/dev instead of /trees/main."""
        get_calls: list[str] = []

        def fake_get(path, **kw):
            get_calls.append(path)
            return {"tree": [{"path": "src/main.py"}]}

        monkeypatch.setattr(patched_client, "get", fake_get)
        monkeypatch.setattr(patched_client, "get_raw", lambda path, *, repo=None: "")

        adapter = ForgejoRepositoryContext(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.fetch(pr_id, target_branch="dev")

        tree_calls = [c for c in get_calls if "/git/trees/" in c]
        assert len(tree_calls) == 1, f"Expected 1 tree call, got {len(tree_calls)}: {get_calls}"
        assert "/git/trees/dev" in tree_calls[0]

    def test_fetch_falls_back_to_main_when_target_branch_empty(self, patched_client, monkeypatch):
        """When target_branch is empty, git tree URL falls back to /trees/main."""
        get_calls: list[str] = []

        def fake_get(path, **kw):
            get_calls.append(path)
            return {"tree": [{"path": "src/main.py"}]}

        monkeypatch.setattr(patched_client, "get", fake_get)
        monkeypatch.setattr(patched_client, "get_raw", lambda path, *, repo=None: "")

        adapter = ForgejoRepositoryContext(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.fetch(pr_id, target_branch="")

        tree_calls = [c for c in get_calls if "/git/trees/" in c]
        assert len(tree_calls) == 1
        assert "/git/trees/main" in tree_calls[0]

    def test_fetch_uses_target_branch_for_conventions_url(self, patched_client, monkeypatch):
        """When target_branch='develop', conventions URL uses /raw/develop/."""
        get_raw_calls: list[str] = []

        def fake_get(path, **kw):
            return {"tree": [{"path": "src/main.py"}, {"path": "CONVENTIONS.md"}]}

        def fake_get_raw(path, *, repo=None):
            get_raw_calls.append(path)
            return "## Conventions\nOK"

        monkeypatch.setattr(patched_client, "get", fake_get)
        monkeypatch.setattr(patched_client, "get_raw", fake_get_raw)

        adapter = ForgejoRepositoryContext(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        adapter.fetch(pr_id, target_branch="develop")

        assert any("/raw/develop/" in c for c in get_raw_calls), (
            f"Expected /raw/develop/ in calls, got {get_raw_calls}"
        )


    def test_fetch_logs_entry_and_return(self, patched_client, caplog):
        """RepositoryContext.fetch logs entry and return at INFO."""
        caplog.set_level(logging.INFO)
        adapter = ForgejoRepositoryContext(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)

        adapter.fetch(pr_id)

        entry = [r.message for r in caplog.records if "RepositoryContext.fetch(" in r.message]
        ret = [r.message for r in caplog.records if "RepositoryContext.fetch return" in r.message]

        assert len(entry) == 1
        assert "o/r#1" in entry[0]

        assert len(ret) == 1
        assert "arch=" in ret[0]
        assert "structure=" in ret[0]
        assert "python=" in ret[0]

    def test_build_fragment_context_logs_entry_and_return(self, patched_client, caplog):
        """build_fragment_context logs entry and return at INFO."""
        caplog.set_level(logging.INFO)
        adapter = ForgejoRepositoryContext(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        ctx = adapter.fetch(pr_id)

        adapter.build_fragment_context(ctx, ["a.py", "b.py"], ["fix: thing"])

        entry = [
            r.message for r in caplog.records
            if r.message.startswith("RepositoryContext.build_fragment_context(")
        ]
        ret = [r.message for r in caplog.records if "build_fragment_context return" in r.message]

        assert len(entry) == 1
        assert "files=2" in entry[0]
        assert "commits=1" in entry[0]

        assert len(ret) == 1
        assert "language=" in ret[0]
        assert "serialized=" in ret[0]
