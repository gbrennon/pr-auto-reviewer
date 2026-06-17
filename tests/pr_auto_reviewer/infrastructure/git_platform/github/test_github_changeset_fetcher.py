"""Tests for GitHubChangesetFetcherAdapter using fake client responses."""

import logging

import pytest

from pr_auto_reviewer.domain.exceptions.empty_diff_error import EmptyDiffError
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.github_http_client import (
    GITHUB_DIFF_MEDIA,
    GITHUB_RAW_MEDIA,
)
from pr_auto_reviewer.infrastructure.git_platform.github.github_changeset_fetcher import (
    GitHubChangesetFetcherAdapter,
)
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider


class _RecordingFakeClient:
    """Fake client that records the (path, headers) of every get_raw call."""

    def __init__(
        self,
        diff: str = "",
        file_contents: dict[str, str] | None = None,
        commits: list[dict] | None = None,
    ) -> None:
        self._diff = diff
        self._file_contents = file_contents or {}
        self._commits = commits or []
        self.get_raw_calls: list[tuple[str, dict | None]] = []
        self.get_calls: list[tuple[str, dict]] = []

    def get_raw(self, path: str, *, headers: dict | None = None) -> str:
        self.get_raw_calls.append((path, headers))
        if path.endswith(".diff") or "/pulls/" in path and path.rsplit("/", 1)[-1].isdigit():
            return self._diff
        return self._file_contents.get(path, "raw content")

    def get(self, path: str, **params) -> dict:
        self.get_calls.append((path, params))
        return self._commits if self._commits else {}


_SAMPLE_DIFF = (
    "diff --git a/src/a.py b/src/a.py\n"
    "--- a/src/a.py\n"
    "+++ b/src/a.py\n"
    "@@ -1,1 +1,1 @@\n"
    "-old line\n"
    "+new line\n"
)


class TestGitHubChangesetFetcherAdapter:

    def test_fetch_returns_diff(self) -> None:
        client = _RecordingFakeClient(diff=_SAMPLE_DIFF)
        adapter = GitHubChangesetFetcherAdapter(client)
        pr_id = PullRequestId(repository="o/r", number=7)
        sha = CommitSha("abc123")

        diff = adapter.fetch(pr_id, sha)

        assert diff.pr_id == pr_id
        assert diff.head_sha == sha
        assert "new line" in diff.diff_content

    def test_fetch_uses_diff_media_type_for_pr_endpoint(self) -> None:
        """The diff request sets Accept: application/vnd.github.v3.diff."""
        client = _RecordingFakeClient(diff=_SAMPLE_DIFF)
        adapter = GitHubChangesetFetcherAdapter(client)
        pr_id = PullRequestId(repository="o/r", number=7)
        sha = CommitSha("abc123")

        adapter.fetch(pr_id, sha)

        diff_call = next(
            (call for call in client.get_raw_calls if "/pulls/7" in call[0]),
            None,
        )
        assert diff_call is not None
        assert diff_call[1] is not None
        assert diff_call[1]["Accept"] == GITHUB_DIFF_MEDIA

    def test_fetch_uses_contents_endpoint_for_file_content(self) -> None:
        """File content is fetched from /contents/{path}?ref={sha}."""
        client = _RecordingFakeClient(diff=_SAMPLE_DIFF)
        adapter = GitHubChangesetFetcherAdapter(client)
        pr_id = PullRequestId(repository="o/r", number=7)
        sha = CommitSha("abc123")

        adapter.fetch(pr_id, sha)

        contents_call = next(
            (
                call for call in client.get_raw_calls
                if "/contents/" in call[0] and "ref=abc123" in call[0]
            ),
            None,
        )
        assert contents_call is not None
        assert contents_call[1] is not None
        assert contents_call[1]["Accept"] == GITHUB_RAW_MEDIA

    def test_fetch_raises_on_empty_diff(self) -> None:
        client = _RecordingFakeClient(diff="")
        adapter = GitHubChangesetFetcherAdapter(client)
        pr_id = PullRequestId(repository="o/r", number=7)
        sha = CommitSha("abc123")

        with pytest.raises(EmptyDiffError):
            adapter.fetch(pr_id, sha)

    def test_fetch_raises_on_short_diff(self) -> None:
        client = _RecordingFakeClient(diff="too short")
        adapter = GitHubChangesetFetcherAdapter(client)
        pr_id = PullRequestId(repository="o/r", number=7)
        sha = CommitSha("abc123")

        with pytest.raises(EmptyDiffError):
            adapter.fetch(pr_id, sha)

    def test_fetch_excludes_dev_null_files(self) -> None:
        diff = (
            "diff --git a/deleted.py b//dev/null\n"
            "diff --git a/kept.py b/kept.py\n"
            "@@ -0,0 +1 @@\n+line\n"
        )
        client = _RecordingFakeClient(diff=diff)
        adapter = GitHubChangesetFetcherAdapter(client)
        pr_id = PullRequestId(repository="o/r", number=7)
        sha = CommitSha("abc123")

        diff_obj = adapter.fetch(pr_id, sha)

        assert "deleted.py" not in diff_obj.file_contents
        assert "kept.py" in diff_obj.file_contents

    def test_fetch_skips_unreadable_file(self) -> None:
        diff = (
            "diff --git a/a.py b/a.py\n"
            "diff --git a/b.py b/b.py\n"
            "@@ -0,0 +1 @@\n+line\n"
        )
        client = _RecordingFakeClient(diff=diff, file_contents={"b.py": "B body"})
        original_get_raw = client.get_raw

        def selective_get_raw(path, *, headers=None):
            if "a.py" in path:
                raise Exception("404 not found")
            return original_get_raw(path, headers=headers)

        client.get_raw = selective_get_raw
        adapter = GitHubChangesetFetcherAdapter(client)
        pr_id = PullRequestId(repository="o/r", number=7)
        sha = CommitSha("abc123")

        diff_obj = adapter.fetch(pr_id, sha)
        assert "a.py" not in diff_obj.file_contents
        assert "b.py" in diff_obj.file_contents

    def test_fetch_collects_commit_subjects(self) -> None:
        diff = _SAMPLE_DIFF
        commits_payload = [
            {"commit": {"message": "feat: add login\n\nlong body"}},
            {"commit": {"message": "fix: handle null"}},
        ]
        client = _RecordingFakeClient(diff=diff)
        client.get = lambda path, **kw: commits_payload
        adapter = GitHubChangesetFetcherAdapter(client)
        pr_id = PullRequestId(repository="o/r", number=7)
        sha = CommitSha("abc123")

        diff_obj = adapter.fetch(pr_id, sha)
        assert diff_obj.commit_messages == ["feat: add login", "fix: handle null"]

    def test_fetch_returns_empty_commit_messages_on_failure(self) -> None:
        diff = _SAMPLE_DIFF
        client = _RecordingFakeClient(diff=diff)

        def raising_get(path, **kw):
            raise Exception("boom")

        client.get = raising_get
        adapter = GitHubChangesetFetcherAdapter(client)
        pr_id = PullRequestId(repository="o/r", number=7)
        sha = CommitSha("abc123")

        diff_obj = adapter.fetch(pr_id, sha)
        assert diff_obj.commit_messages == []

    def test_fetch_logs_entry_and_return(self, caplog) -> None:
        caplog.set_level(logging.INFO)
        client = _RecordingFakeClient(diff=_SAMPLE_DIFF)
        adapter = GitHubChangesetFetcherAdapter(client)
        pr_id = PullRequestId(
            repository="o/r", number=7, platform=GitProvider.GITHUB,
        )
        sha = CommitSha("abc123")

        adapter.fetch(pr_id, sha)

        entry = [
            r.message for r in caplog.records
            if "GitHubChangesetFetcher.fetch(" in r.message
        ]
        ret = [
            r.message for r in caplog.records
            if "GitHubChangesetFetcher return" in r.message
        ]
        assert len(entry) == 1
        assert "pr_id=github:o/r#7" in entry[0]
        assert len(ret) == 1
        assert "pr=github:o/r#7" in ret[0]
