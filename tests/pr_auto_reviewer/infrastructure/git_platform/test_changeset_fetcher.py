"""Tests for ForgejoChangesetFetcher using fixture data."""

import logging

import pytest

from pr_auto_reviewer.domain.exceptions.empty_diff_error import EmptyDiffError
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.forgejo.changeset_fetcher import (
    ForgejoChangesetFetcher,
)
from pr_auto_reviewer.infrastructure.github.changeset_fetcher import (
    GithubChangesetFetcher,
)

class TestForgejoChangesetFetcher:
    """Tests for ForgejoChangesetFetcher using captured fixture data."""

    def test_fetch_returns_diff(self, patched_client):
        """Fetch returns PullRequestDiff with content."""
        adapter = ForgejoChangesetFetcher(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        diff = adapter.fetch(pr_id, sha)

        assert diff.pr_id == pr_id
        assert diff.head_sha == sha
        assert len(diff.diff_content) > 100

    def test_fetch_raises_on_empty_diff(self, patched_client, monkeypatch):
        """Raises EmptyDiffError when diff is empty."""
        monkeypatch.setattr(patched_client, "get_raw", lambda path, **kw: "")
        adapter = ForgejoChangesetFetcher(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        with pytest.raises(EmptyDiffError):
            adapter.fetch(pr_id, sha)

    def test_fetch_raises_on_short_diff(self, patched_client, monkeypatch):
        """Raises EmptyDiffError when diff is too short."""
        monkeypatch.setattr(patched_client, "get_raw", lambda path, **kw: "short")
        adapter = ForgejoChangesetFetcher(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        with pytest.raises(EmptyDiffError):
            adapter.fetch(pr_id, sha)

    def test_fetch_excludes_dev_null(self, patched_client, monkeypatch):
        """Deleted files (b/dev/null) are excluded."""
        monkeypatch.setattr(patched_client, "get_raw", lambda path, **kw: (
            "diff --git a/deleted.py b//dev/null\n"
            "diff --git a/kept.py b/kept.py\n"
            "@@ -0,0 +1 @@\n+line\n"
        ))
        adapter = ForgejoChangesetFetcher(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        diff = adapter.fetch(pr_id, sha)
        assert "deleted.py" not in diff.file_contents

    def test_fetch_excludes_same_path_deletion(self, patched_client, monkeypatch):
        """Deleted files with same a/ and b/ path (+++ /dev/null in body) are excluded."""
        call_count = [0]

        def fake_get_raw(path, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return (
                    "diff --git a/deleted.py b/deleted.py\n"
                    "deleted file mode 100644\n"
                    "--- a/deleted.py\n"
                    "+++ /dev/null\n"
                    "@@ -1 +0,0 @@\n"
                    "-old line\n"
                    "diff --git a/kept.py b/kept.py\n"
                    "--- a/kept.py\n"
                    "+++ b/kept.py\n"
                    "@@ -0,0 +1 @@\n"
                    "+new line\n"
                )
            if "kept.py" in path:
                return "new line"
            raise AssertionError(f"Should not fetch deleted file: {path}")

        monkeypatch.setattr(patched_client, "get_raw", fake_get_raw)
        adapter = ForgejoChangesetFetcher(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        diff = adapter.fetch(pr_id, sha)
        assert "deleted.py" not in diff.file_contents
        assert "kept.py" in diff.file_contents

    def test_fetch_skips_unreadable_file(self, patched_client, monkeypatch):
        """Unreadable file is silently skipped."""
        call_count = [0]
        def fake_get_raw(path, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return "diff --git a/a.py b/a.py\ndiff --git a/b.py b/b.py\n@@ -0,0 +1 @@\n+line\n"
            if "a.py" in path:
                raise Exception("404")
            return "content"
        monkeypatch.setattr(patched_client, "get_raw", fake_get_raw)
        adapter = ForgejoChangesetFetcher(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        diff = adapter.fetch(pr_id, sha)
        assert "a.py" not in diff.file_contents
        assert "b.py" in diff.file_contents

    def test_fetch_logs_entry_and_return(self, patched_client, caplog):
        """Entry and return are logged at INFO level."""
        caplog.set_level(logging.INFO)
        adapter = ForgejoChangesetFetcher(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        adapter.fetch(pr_id, sha)

        entry = [r.message for r in caplog.records if "ChangesetFetcher.fetch(" in r.message]
        ret = [r.message for r in caplog.records if "ChangesetFetcher return" in r.message]

        assert len(entry) == 1
        assert "pr_id=o/r#1" in entry[0]
        assert "sha=abc123" in entry[0]

        assert len(ret) == 1
        assert "pr=o/r#1" in ret[0]
        assert "sha=abc123" in ret[0]
        assert "diff=" in ret[0]
        assert "files=" in ret[0]

    def test_fetch_commit_messages_parses_subject(self, patched_client, monkeypatch):
        """Commit messages are parsed: only subject line extracted."""
        commits_data = [
            {"commit": {"message": "fix: crash on null\n\nLong body here"}},
            {"commit": {"message": "feat: add login"}},
        ]
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: commits_data)
        adapter = ForgejoChangesetFetcher(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        diff = adapter.fetch(pr_id, sha)
        assert diff.commit_messages == ["fix: crash on null", "feat: add login"]

    def test_fetch_commit_messages_survives_error(self, patched_client, monkeypatch):
        """If commit fetch fails, returns empty list."""
        monkeypatch.setattr(patched_client, "get", lambda path, **kw: (_ for _ in ()).throw(
            Exception("boom")
        ))
        adapter = ForgejoChangesetFetcher(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        diff = adapter.fetch(pr_id, sha)
        assert diff.commit_messages == []

    def test_fetch_github_diff_accept_header(self, monkeypatch):
        """GitHub client gets Accept header for diff."""
        captured_diff_header = {}

        class FakeGitHubClient:
            _platform_mode = "github"

            def get_raw(self, path, headers=None, *, repo=None):
                if ".diff" in path:
                    captured_diff_header.update(headers or {})
                    return "diff --git a/x.py b/x.py\n@@ -1,5 +1,5 @@\n-old\n+new\n context line here\n context line here\n context line here\n context line here\n context line here\n context line here\n context line here\n"
                return ""

            def get(self, path, **kw):
                return []

            def _get_auth_header(self):
                return {"Authorization": "Bearer tok"}

        adapter = GithubChangesetFetcher(FakeGitHubClient())
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        adapter.fetch(pr_id, sha)
        assert captured_diff_header.get("Accept") == "application/vnd.github.diff"

    def test_fetch_github_raw_content(self, monkeypatch):
        """GitHub mode fetches raw content via Contents API with raw+json accept."""
        class FakeGitHubClient:
            _platform_mode = "github"

            def get_raw(self, path, headers=None, *, repo=None):
                if ".diff" in path:
                    return "diff --git a/x.py b/x.py\n@@ -1,5 +1,5 @@\n-old line here\n+new line here\n context line here\n context line here\n context line here\n context line here\n context line here\n context line here\n context line here\n"
                if path.startswith("/repos/o/r/contents/x.py?ref="):
                    header_accept = (headers or {}).get("Accept", "")
                    assert header_accept == "application/vnd.github.raw+json"
                return "print('hello')"

            def get(self, path, **kw):
                return [{"commit": {"message": "fix"}}]

            def _get_auth_header(self):
                return {"Authorization": "Bearer tok"}

        adapter = GithubChangesetFetcher(FakeGitHubClient())
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        diff = adapter.fetch(pr_id, sha)
        assert "x.py" in diff.file_contents
        assert diff.file_contents["x.py"] == "print('hello')"

    def test_fetch_github_raw_error_skipped(self, monkeypatch):
        """GitHub raw content fetch error skips file silently."""
        class FakeGitHubClient:
            _platform_mode = "github"

            def get_raw(self, path, headers=None, *, repo=None):
                if ".diff" in path:
                    return "diff --git a/x.py b/x.py\n@@ -1,5 +1,5 @@\n-old line here\n+new line here\n context line here\n context line here\n context line here\n context line here\n context line here\n context line here\n context line here\n"
                if "/contents/" in path:
                    raise Exception("404")
                return ""

            def get(self, path, **kw):
                return []

            def _get_auth_header(self):
                return {"Authorization": "Bearer tok"}

        adapter = GithubChangesetFetcher(FakeGitHubClient())
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        diff = adapter.fetch(pr_id, sha)
        assert diff.file_contents == {}

    # ── _DELETION_RE (+++ /dev/null) edge-case coverage ──────────────

    def test_fetch_excludes_nested_deletion(self, patched_client, monkeypatch):
        """Nested paths (src/sub/deleted.py) with +++ /dev/null are excluded."""
        monkeypatch.setattr(patched_client, "get_raw", lambda path, **kw: (
            "diff --git a/src/sub/deleted.py b/src/sub/deleted.py\n"
            "--- a/src/sub/deleted.py\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-old code\n"
        ))
        adapter = ForgejoChangesetFetcher(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        diff = adapter.fetch(pr_id, sha)
        assert "src/sub/deleted.py" not in diff.file_contents
        assert len(diff.file_contents) == 0

    def test_fetch_excludes_multiple_deletions(self, patched_client, monkeypatch):
        """Multiple +++ /dev/null deletions in one diff are all excluded."""
        monkeypatch.setattr(patched_client, "get_raw", lambda path, **kw: (
            "diff --git a/a.py b/a.py\n"
            "--- a/a.py\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-old a\n"
            "diff --git a/b.py b/b.py\n"
            "--- a/b.py\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-old b\n"
            "diff --git a/c.py b/c.py\n"
            "--- a/c.py\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-old c\n"
        ))
        adapter = ForgejoChangesetFetcher(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        diff = adapter.fetch(pr_id, sha)
        assert len(diff.file_contents) == 0

    def test_fetch_excludes_deletion_with_nonstandard_path(self, patched_client, monkeypatch):
        """File path with dots and dashes (package-lock.json) with +++ /dev/null is excluded."""
        call_count = [0]

        def fake_get_raw(path, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                return (
                    "diff --git a/package-lock.json b/package-lock.json\n"
                    "--- a/package-lock.json\n"
                    "+++ /dev/null\n"
                    "@@ -1 +0,0 @@\n"
                    "-old lock\n"
                    "diff --git a/src/utils.py b/src/utils.py\n"
                    "--- a/src/utils.py\n"
                    "+++ b/src/utils.py\n"
                    "@@ -0,0 +1 @@\n"
                    "+new util\n"
                )
            if "utils.py" in path:
                return "new util"
            raise AssertionError(f"Should not fetch deleted file: {path}")

        monkeypatch.setattr(patched_client, "get_raw", fake_get_raw)
        adapter = ForgejoChangesetFetcher(patched_client)
        pr_id = PullRequestId(repository="o/r", number=1)
        sha = CommitSha("abc123")

        diff = adapter.fetch(pr_id, sha)
        assert "package-lock.json" not in diff.file_contents
        assert "src/utils.py" in diff.file_contents
