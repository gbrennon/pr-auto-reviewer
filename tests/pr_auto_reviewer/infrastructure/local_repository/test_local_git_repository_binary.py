from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pr_auto_reviewer.infrastructure.local_repository.local_git_repository import (
    LocalGitRepository,
)

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git is not installed on this runner",
)


class TestLocalGitRepositoryBinary:
    """Exercises binary and non-UTF-8 file handling in LocalGitRepository."""

    def test_read_file_raises_runtime_error_on_binary_file(
        self, tmp_path: Path,
    ) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        (repo_path / "image.gif").write_bytes(
            b"GIF89a\x97\x00\x10\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!",
        )
        self._git_commit_file(repo_path, "image.gif")
        sut = LocalGitRepository(tmp_path / "clones")

        with pytest.raises(RuntimeError, match="Binary"):
            sut.read_file(repo_path, "image.gif", ref="HEAD")

    def test_read_file_raises_runtime_error_on_null_bytes(
        self, tmp_path: Path,
    ) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        (repo_path / "data.bin").write_bytes(b"hello\x00world")
        self._git_commit_file(repo_path, "data.bin")
        sut = LocalGitRepository(tmp_path / "clones")

        with pytest.raises(RuntimeError, match="Binary"):
            sut.read_file(repo_path, "data.bin", ref="HEAD")

    def test_compute_diff_with_binary_files_does_not_raise(
        self, tmp_path: Path,
    ) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        base_sha = self._head_sha(repo_path)
        subprocess.run(
            ["git", "-C", str(repo_path), "checkout", "-b", "feature"],
            check=True,
            capture_output=True,
            text=True,
        )
        (repo_path / "image.gif").write_bytes(
            b"GIF89a\x97\x00\x10\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!",
        )
        self._git_commit_file(repo_path, "image.gif")
        head_sha = self._head_sha(repo_path)
        sut = LocalGitRepository(tmp_path / "clones")

        diff = sut.compute_diff(repo_path, base_sha, head_sha)

        assert "image.gif" in diff

    def _init_repo(self, base: Path, name: str) -> Path:
        repo_path = base / name
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
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
        subprocess.run(
            ["git", "-C", str(repo_path), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
            text=True,
        )
        (repo_path / "README.md").write_text("# Test Repo\n")
        self._git_commit_file(repo_path, "README.md")
        return repo_path

    def _git_commit_file(self, repo_path: Path, filename: str) -> None:
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

    def _head_sha(self, repo_path: Path) -> str:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
