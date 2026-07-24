"""Tests for LocalChangesetFetcher orchestration logic."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pr_auto_reviewer.application.ports.outbound.local_repository_port import (
    LocalRepositoryPort,
)
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.local_repository.local_changeset_fetcher import (
    LocalChangesetFetcher,
)


class TestLocalChangesetFetcher:
    """Tests for LocalChangesetFetcher using a mocked LocalRepositoryPort."""

    def _make_sample_diff(self, with_deletion: bool = False) -> str:
        """Build a sample unified diff with optional deletion header."""
        lines = [
            "diff --git a/src/foo.py b/src/foo.py",
            "@@ -1,3 +1,4 @@",
            "+new line",
            "diff --git a/src/bar.py b/src/bar.py",
            "@@ -1,2 +1,3 @@",
            "+another line",
        ]
        if with_deletion:
            lines.insert(0, "--- a/deleted.py")
            lines.insert(1, "+++ /dev/null")
        return "\n".join(lines)

    def _make_repo(self) -> MagicMock:
        """Create a fully-stubbed LocalRepositoryPort mock."""
        repo = MagicMock(spec=LocalRepositoryPort)
        repo.clone.return_value = Path("/tmp/clone/repo")
        repo.compute_diff.return_value = self._make_sample_diff()
        repo.commit_messages.return_value = ["fix: stuff"]
        repo.resolve_base_sha.return_value = "abc123"
        repo.read_file.return_value = "print('hello')"
        return repo

    def test_fetch_returns_pull_request_diff_with_correct_fields(self) -> None:
        """Fetch returns a PullRequestDiff carrying all expected fields."""
        repo = MagicMock(spec=LocalRepositoryPort)
        repo.clone.return_value = Path("/tmp/clone/repo")
        repo.compute_diff.return_value = self._make_sample_diff()
        repo.commit_messages.return_value = ["fix: stuff"]
        repo.resolve_base_sha.return_value = "abc123"
        repo.read_file.return_value = "print('hello')"

        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, platform_mode="codeberg")

        result = fetcher.fetch(pr_id, sha)

        assert isinstance(result, PullRequestDiff)
        assert result.pr_id == pr_id
        assert result.head_sha == sha
        assert result.diff_content == self._make_sample_diff()
        assert result.file_contents == {
            "src/bar.py": "print('hello')",
            "src/foo.py": "print('hello')",
        }
        assert result.commit_messages == ["fix: stuff"]

    def test_fetch_calls_clone_with_correct_url(self) -> None:
        """Clone is called with the PR id and the configured platform clone URL."""
        repo = self._make_repo()
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, platform_mode="codeberg")

        fetcher.fetch(pr_id, sha)

        repo.clone.assert_called_once_with(
            pr_id, "https://codeberg.org/test-org/test-repo.git"
        )

    def test_fetch_keeps_repo_for_multi_turn(self) -> None:
        """Repository is NOT removed after fetch — clone persists for multi-turn reuse."""
        repo = self._make_repo()
        repo.compute_diff.side_effect = RuntimeError("git diff failed")
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, platform_mode="codeberg")

        with pytest.raises(RuntimeError, match="git diff failed"):
            fetcher.fetch(pr_id, sha)

        repo.remove.assert_not_called()

    def test_fetch_parses_file_paths_from_diff(self) -> None:
        """Non-deleted file paths from the diff are read and returned in file_contents."""
        repo = self._make_repo()
        repo.compute_diff.return_value = self._make_sample_diff(with_deletion=True)
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, platform_mode="codeberg")

        result = fetcher.fetch(pr_id, sha)

        assert "deleted.py" not in result.file_contents
        assert "src/foo.py" in result.file_contents
        assert "src/bar.py" in result.file_contents
        assert repo.read_file.call_count == 2

    def test_fetch_skips_unreadable_files(self) -> None:
        """Files that raise RuntimeError on read are skipped with a warning."""
        repo = self._make_repo()

        def read_side_effect(repo_path, file_path, ref=None):
            if file_path == "src/bar.py":
                raise RuntimeError("permission denied")
            return "print('hello')"

        repo.read_file.side_effect = read_side_effect
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, platform_mode="codeberg")

        result = fetcher.fetch(pr_id, sha)

        assert "src/bar.py" not in result.file_contents
        assert "src/foo.py" in result.file_contents
        assert result.file_contents["src/foo.py"] == "print('hello')"

    def test_fetch_platform_mode_affects_clone_url(self) -> None:
        """The platform_mode controls which _CLONE_URLS template is used."""
        repo_codeberg = self._make_repo()
        repo_github = self._make_repo()
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        LocalChangesetFetcher(
            local_repository=repo_codeberg, platform_mode="codeberg"
        ).fetch(pr_id, sha)
        LocalChangesetFetcher(
            local_repository=repo_github, platform_mode="github"
        ).fetch(pr_id, sha)

        repo_codeberg.clone.assert_called_once_with(
            pr_id, "https://codeberg.org/test-org/test-repo.git"
        )
        repo_github.clone.assert_called_once_with(
            pr_id, "https://github.com/test-org/test-repo.git"
        )

    def test_fetch_empty_diff_returns_empty_contents(self) -> None:
        """A diff containing no file-path lines yields an empty file_contents dict."""
        repo = self._make_repo()
        repo.compute_diff.return_value = "just some header\ndiff --git\nno match here"
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, platform_mode="codeberg")

        result = fetcher.fetch(pr_id, sha)

        assert result.file_contents == {}
        repo.read_file.assert_not_called()

    def test_fetch_passes_pr_head_ref_for_read_file(self) -> None:
        """read_file is called with ref set to the PR head ref (pr-{number})."""
        repo = self._make_repo()
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, platform_mode="codeberg")

        fetcher.fetch(pr_id, sha)

        read_file_calls = repo.read_file.call_args_list
        assert len(read_file_calls) >= 1
        for call in read_file_calls:
            assert call.kwargs["ref"] == "pr-42"
