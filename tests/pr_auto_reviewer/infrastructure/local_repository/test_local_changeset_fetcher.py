"""Tests for LocalChangesetFetcher orchestration logic."""

from pathlib import Path

import pytest

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.local_repository.local_changeset_fetcher import (
    LocalChangesetFetcher,
)
from tests.fakes.clone_url_resolver_fakes import FakeCloneUrlResolver
from tests.fakes.local_repository_fakes import FakeLocalRepository

class TestLocalChangesetFetcher:
    """Tests for LocalChangesetFetcher using a FakeLocalRepository."""

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

    def _make_repo(self) -> FakeLocalRepository:
        """Create a fully-stubbed LocalRepositoryPort fake."""
        return FakeLocalRepository(
            clone_return=Path("/tmp/clone/repo"),
            compute_diff_return=self._make_sample_diff(),
            commit_messages_return=["fix: stuff"],
            resolve_base_sha_return="abc123",
            read_file_return="print('hello')",
        )

    def test_fetch_returns_pull_request_diff_with_correct_fields(self) -> None:
        """Fetch returns a PullRequestDiff carrying all expected fields."""
        repo = FakeLocalRepository(
            clone_return=Path("/tmp/clone/repo"),
            compute_diff_return=self._make_sample_diff(),
            commit_messages_return=["fix: stuff"],
            resolve_base_sha_return="abc123",
            read_file_return="print('hello')",
        )

        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, url_resolver=FakeCloneUrlResolver("codeberg")  )

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

        fetcher = LocalChangesetFetcher(local_repository=repo, url_resolver=FakeCloneUrlResolver("codeberg")  )

        fetcher.fetch(pr_id, sha)

        assert repo.clone_calls == [((pr_id, "https://codeberg.org/test-org/test-repo.git"), {})]

    def test_fetch_keeps_repo_for_multi_turn(self) -> None:
        """Repository is NOT removed after fetch — clone persists for multi-turn reuse."""
        repo = self._make_repo()
        repo.compute_diff_return = RuntimeError("git diff failed")
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, url_resolver=FakeCloneUrlResolver("codeberg")  )

        with pytest.raises(RuntimeError, match="git diff failed"):
            fetcher.fetch(pr_id, sha)

        assert len(repo.remove_calls) == 0

    def test_fetch_parses_file_paths_from_diff(self) -> None:
        """Non-deleted file paths from the diff are read and returned in file_contents."""
        repo = self._make_repo()
        repo.compute_diff_return = self._make_sample_diff(with_deletion=True)
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, url_resolver=FakeCloneUrlResolver("codeberg")  )

        result = fetcher.fetch(pr_id, sha)

        assert "deleted.py" not in result.file_contents
        assert "src/foo.py" in result.file_contents
        assert "src/bar.py" in result.file_contents
        assert len(repo.read_file_calls) == 2

    def test_fetch_skips_unreadable_files(self) -> None:
        """Files that raise RuntimeError on read are skipped with a warning."""
        repo = self._make_repo()

        repo.read_file_return = [
            RuntimeError("permission denied"),
            "print('hello')",
        ]
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, url_resolver=FakeCloneUrlResolver("codeberg")  )

        result = fetcher.fetch(pr_id, sha)

        assert "src/bar.py" not in result.file_contents
        assert "src/foo.py" in result.file_contents
        assert result.file_contents["src/foo.py"] == "print('hello')"

    def test_fetch_platform_mode_affects_clone_url(self) -> None:
        """The url_resolver controls which clone URL template is used."""
        repo_codeberg = self._make_repo()
        repo_github = self._make_repo()
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        LocalChangesetFetcher(
            local_repository=repo_codeberg, url_resolver=FakeCloneUrlResolver("codeberg")  
        ).fetch(pr_id, sha)
        LocalChangesetFetcher(
            local_repository=repo_github, url_resolver=FakeCloneUrlResolver("github")  
        ).fetch(pr_id, sha)

        assert repo_codeberg.clone_calls == [
            ((pr_id, "https://codeberg.org/test-org/test-repo.git"), {})
        ]
        assert repo_github.clone_calls == [
            ((pr_id, "https://github.com/test-org/test-repo.git"), {})
        ]

    def test_fetch_empty_diff_returns_empty_contents(self) -> None:
        """A diff containing no file-path lines yields an empty file_contents dict."""
        repo = self._make_repo()
        repo.compute_diff_return = "just some header\ndiff --git\nno match here"
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, url_resolver=FakeCloneUrlResolver("codeberg")  )

        result = fetcher.fetch(pr_id, sha)

        assert result.file_contents == {}
        assert len(repo.read_file_calls) == 0

    def test_fetch_passes_pr_head_ref_for_read_file(self) -> None:
        """read_file is called with ref set to the PR head ref (pr-{number})."""
        repo = self._make_repo()
        pr_id = PullRequestId("test-org/test-repo", 42)
        sha = CommitSha("def456")

        fetcher = LocalChangesetFetcher(local_repository=repo, url_resolver=FakeCloneUrlResolver("codeberg")  )

        fetcher.fetch(pr_id, sha)

        read_file_calls = repo.read_file_calls
        assert len(read_file_calls) >= 1
        for call_args, call_kwargs in read_file_calls:
            assert call_kwargs["ref"] == "pr-42"
