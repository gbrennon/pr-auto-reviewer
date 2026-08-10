"""Integration tests for LocalGitRepository — real git operations, no mocks.

These tests require ``git`` on PATH. They are skipped when git is not
installed so they do not break CI/CD runners that lack git.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.local_repository.local_git_repository import (
    LocalGitRepository,
)

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git is not installed on this runner",
)


class TestLocalGitRepository:
    def _configure_git(self, repo_path: Path) -> None:
        subprocess.run(
            ["git", "-C", str(repo_path), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_path), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
            text=True,
        )

    def _create_commit(self, repo_path: Path, filename: str, content: str) -> None:
        file_path = repo_path / filename
        file_path.write_text(content)
        subprocess.run(
            ["git", "-C", str(repo_path), "add", filename],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_path), "commit", "-m", f"Add {filename}"],
            check=True,
            capture_output=True,
            text=True,
        )

    def _get_head_sha(self, repo_path: Path) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _get_rev_parse(self, repo_path: Path, ref: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", ref],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _init_repo(self, base: Path, name: str) -> Path:
        repo_path = base / name
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._configure_git(repo_path)
        self._create_commit(repo_path, "README.md", "# Test Repo")
        return repo_path

    def test_clone_creates_directory_and_returns_path(self, tmp_path: Path) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        sut = LocalGitRepository(tmp_path / "clones")
        result = sut.clone(PullRequestId("owner/repo", 42), str(repo_path))

        assert result.exists()
        assert result == sut.last_clone_path

    def test_clone_idempotent_does_fetch_not_reclone(self, tmp_path: Path) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        sut = LocalGitRepository(tmp_path / "clones")
        first = sut.clone(PullRequestId("owner/repo", 42), str(repo_path))

        sentinel = first / "sentinel"
        sentinel.write_text("marker")
        sut.clone(PullRequestId("owner/repo", 42), str(repo_path))

        assert sentinel.exists()

    def test_clone_fetches_pr_ref_when_available(self, tmp_path: Path) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        subprocess.run(
            ["git", "-C", str(repo_path), "checkout", "-b", "pull/42/head"],
            check=True,
            capture_output=True,
            text=True,
        )

        sut = LocalGitRepository(tmp_path / "clones")
        clone_path = sut.clone(PullRequestId("owner/repo", 42), str(repo_path))

        assert sut._pr_refs[clone_path] == "pr-42"

    def test_remove_deletes_directory(self, tmp_path: Path) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        sut = LocalGitRepository(tmp_path / "clones")
        clone_path = sut.clone(PullRequestId("owner/repo", 42), str(repo_path))
        assert clone_path.exists()

        sut.remove(clone_path)

        assert not clone_path.exists()
        assert sut.last_clone_path is None

    def test_compute_diff_between_commits(self, tmp_path: Path) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        base_sha = self._get_head_sha(repo_path)

        subprocess.run(
            ["git", "-C", str(repo_path), "checkout", "-b", "feature"],
            check=True,
            capture_output=True,
            text=True,
        )
        self._create_commit(repo_path, "a.py", "print('hello')")
        head_sha = self._get_head_sha(repo_path)

        sut = LocalGitRepository(tmp_path / "clones")
        diff = sut.compute_diff(repo_path, base_sha, head_sha)

        assert "print('hello')" in diff

    def test_commit_messages_returns_correct_list(self, tmp_path: Path) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        base_sha = self._get_head_sha(repo_path)

        subprocess.run(
            ["git", "-C", str(repo_path), "checkout", "-b", "feature"],
            check=True,
            capture_output=True,
            text=True,
        )
        self._create_commit(repo_path, "a.py", "print('hello')")
        self._create_commit(repo_path, "b.py", "print('world')")
        head_sha = self._get_head_sha(repo_path)

        sut = LocalGitRepository(tmp_path / "clones")
        messages = sut.commit_messages(repo_path, base_sha, head_sha)

        assert len(messages) == 2
        assert messages[0] == "Add b.py"
        assert messages[1] == "Add a.py"

    def test_read_file_returns_file_content(self, tmp_path: Path) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        sut = LocalGitRepository(tmp_path / "clones")
        content = sut.read_file(repo_path, "README.md", ref="HEAD")

        assert content.strip() == "# Test Repo"

    def test_read_file_uses_pr_ref_mapping(self, tmp_path: Path) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        subprocess.run(
            ["git", "-C", str(repo_path), "checkout", "-b", "some-branch"],
            check=True,
            capture_output=True,
            text=True,
        )
        (repo_path / "README.md").write_text("branch content")
        subprocess.run(
            ["git", "-C", str(repo_path), "add", "README.md"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_path), "commit", "-m", "Update on branch"],
            check=True,
            capture_output=True,
            text=True,
        )
        branch_sha = self._get_head_sha(repo_path)

        sut = LocalGitRepository(tmp_path / "clones")
        clone_path = sut.clone(PullRequestId("owner/repo", 42), str(repo_path))
        sut._pr_refs[clone_path] = branch_sha

        content = sut.read_file(clone_path, "README.md")

        assert content.strip() == "branch content"

    def test_resolve_base_sha_returns_merge_base(self, tmp_path: Path) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        base_sha = self._get_head_sha(repo_path)

        sut = LocalGitRepository(tmp_path / "clones")
        clone_path = sut.clone(PullRequestId("owner/repo", 42), str(repo_path))
        sut._pr_refs[clone_path] = base_sha

        resolved = sut.resolve_base_sha(clone_path, 42)

        assert resolved == base_sha

    def test_run_git_nonzero_raises_runtime_error(self, tmp_path: Path) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        sut = LocalGitRepository(tmp_path / "clones")

        with pytest.raises(RuntimeError, match="git .* failed"):
            sut._run_git(repo_path, "log", "--nonexistent-flag")

    def test_list_tree_returns_file_list(self, tmp_path: Path) -> None:
        """list_tree returns the list of tracked files at a ref."""
        repo_path = self._init_repo(tmp_path, "source")
        (repo_path / "src").mkdir()
        self._create_commit(repo_path, "src/main.py", "print('hello')")
        sut = LocalGitRepository(tmp_path / "clones")
        files = sut.list_tree(repo_path, ref="HEAD")

        assert "README.md" in files
        assert "src/main.py" in files
