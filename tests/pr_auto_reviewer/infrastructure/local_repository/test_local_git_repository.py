"""Integration tests for LocalGitRepository — real git operations, no mocks."""

from __future__ import annotations

import subprocess
from pathlib import Path

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.local_repository.local_git_repository import (
    LocalGitRepository,
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
        file_path.parent.mkdir(parents=True, exist_ok=True)
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

    def test_clone_creates_directory_and_returns_path(self, tmp_path: Path) -> None:
        """Clone creates the destination directory and returns its path."""
        repo_path = tmp_path / "source"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._configure_git(repo_path)
        self._create_commit(repo_path, "README.md", "# Test")

        pr_id = PullRequestId("test-org/test-repo", 42)
        sut = LocalGitRepository(temp_base_dir=tmp_path / "clones")

        clone_path = sut.clone(pr_id, f"file://{repo_path}")

        assert clone_path.exists()
        assert sut.last_clone_path == clone_path

    def test_clone_idempotent_does_fetch_not_reclone(self, tmp_path: Path) -> None:
        """Second clone call fetches instead of re-cloning when directory exists."""
        repo_path = tmp_path / "source"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._configure_git(repo_path)
        self._create_commit(repo_path, "README.md", "# Test")

        pr_id = PullRequestId("test-org/test-repo", 42)
        sut = LocalGitRepository(temp_base_dir=tmp_path / "clones")

        first_clone = sut.clone(pr_id, f"file://{repo_path}")

        sentinel = first_clone / ".sentinel"
        sentinel.write_text("marker")

        self._create_commit(repo_path, "CHANGELOG.md", "v2")

        second_clone = sut.clone(pr_id, f"file://{repo_path}")

        assert first_clone == second_clone
        assert sentinel.exists()

    def test_clone_fetches_pr_ref_when_available(self, tmp_path: Path) -> None:
        """Clone sets _pr_refs when the source has the expected PR ref."""
        repo_path = tmp_path / "source"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._configure_git(repo_path)
        self._create_commit(repo_path, "README.md", "# Test")

        subprocess.run(
            ["git", "-C", str(repo_path), "checkout", "-b", "pull/42/head"],
            check=True,
            capture_output=True,
            text=True,
        )

        pr_id = PullRequestId("test-org/test-repo", 42)
        sut = LocalGitRepository(temp_base_dir=tmp_path / "clones")

        clone_path = sut.clone(pr_id, f"file://{repo_path}")

        assert clone_path in sut._pr_refs
        assert sut._pr_refs[clone_path] == "pr-42"

    def test_remove_deletes_directory(self, tmp_path: Path) -> None:
        """Remove deletes the cloned directory and clears last_clone_path."""
        repo_path = tmp_path / "source"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._configure_git(repo_path)
        self._create_commit(repo_path, "README.md", "# Test")

        pr_id = PullRequestId("test-org/test-repo", 42)
        sut = LocalGitRepository(temp_base_dir=tmp_path / "clones")

        clone_path = sut.clone(pr_id, f"file://{repo_path}")
        assert clone_path.exists()

        sut.remove(clone_path)

        assert not clone_path.exists()
        assert sut.last_clone_path is None

    def test_compute_diff_between_commits(self, tmp_path: Path) -> None:
        """compute_diff returns the diff between two commit SHAs."""
        repo_path = tmp_path / "source"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._configure_git(repo_path)
        self._create_commit(repo_path, "README.md", "# Test")

        base_sha = self._get_head_sha(repo_path)

        subprocess.run(
            ["git", "-C", str(repo_path), "checkout", "-b", "feature"],
            check=True,
            capture_output=True,
            text=True,
        )
        self._create_commit(repo_path, "src/main.py", "print('hello')")

        head_sha = self._get_head_sha(repo_path)

        sut = LocalGitRepository(temp_base_dir=tmp_path / "clones")

        diff = sut.compute_diff(repo_path, base_sha, head_sha)

        assert "src/main.py" in diff
        assert "print('hello')" in diff

    def test_commit_messages_returns_correct_list(self, tmp_path: Path) -> None:
        """commit_messages returns the subject lines of commits in range."""
        repo_path = tmp_path / "source"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._configure_git(repo_path)
        self._create_commit(repo_path, "README.md", "# Test")

        base_sha = self._get_head_sha(repo_path)

        subprocess.run(
            ["git", "-C", str(repo_path), "checkout", "-b", "feature"],
            check=True,
            capture_output=True,
            text=True,
        )
        self._create_commit(repo_path, "a.py", "a")
        self._create_commit(repo_path, "b.py", "b")

        head_sha = self._get_head_sha(repo_path)

        sut = LocalGitRepository(temp_base_dir=tmp_path / "clones")

        messages = sut.commit_messages(repo_path, base_sha, head_sha)

        assert len(messages) == 2
        assert messages[0] == "Add b.py"
        assert messages[1] == "Add a.py"

    def test_read_file_returns_file_content(self, tmp_path: Path) -> None:
        """read_file returns the content of a committed file at a ref."""
        repo_path = tmp_path / "source"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._configure_git(repo_path)
        self._create_commit(repo_path, "README.md", "# Test Repo")

        sut = LocalGitRepository(temp_base_dir=tmp_path / "clones")

        content = sut.read_file(repo_path, "README.md", "HEAD")

        assert content.strip() == "# Test Repo"

    def test_read_file_uses_pr_ref_mapping(self, tmp_path: Path) -> None:
        """read_file uses _pr_refs mapping as the effective ref."""
        repo_path = tmp_path / "source"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._configure_git(repo_path)
        self._create_commit(repo_path, "README.md", "main branch content")

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

        subprocess.run(
            ["git", "-C", str(repo_path), "checkout", "main"],
            check=True,
            capture_output=True,
            text=True,
        )

        sut = LocalGitRepository(temp_base_dir=tmp_path / "clones")
        sut._pr_refs[repo_path] = "some-branch"

        content = sut.read_file(repo_path, "README.md", "HEAD")

        assert content.strip() == "branch content"

    def test_resolve_base_sha_returns_merge_base(self, tmp_path: Path) -> None:
        """resolve_base_sha returns the merge-base between origin/HEAD and pr-N."""
        repo_path = tmp_path / "source"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._configure_git(repo_path)
        self._create_commit(repo_path, "README.md", "# Test")

        base_sha = self._get_head_sha(repo_path)

        pr_id = PullRequestId("test-org/test-repo", 42)
        sut = LocalGitRepository(temp_base_dir=tmp_path / "clones")
        clone_path = sut.clone(pr_id, f"file://{repo_path}")

        self._configure_git(clone_path)
        subprocess.run(
            ["git", "-C", str(clone_path), "checkout", "-b", "pr-42"],
            check=True,
            capture_output=True,
            text=True,
        )
        self._create_commit(clone_path, "feature.py", "print('feature')")

        resolved = sut.resolve_base_sha(clone_path, 42)

        assert resolved == base_sha

    def test_resolve_base_sha_falls_back_to_origin_head(self, tmp_path: Path) -> None:
        """resolve_base_sha falls back to origin/HEAD when no common ancestor."""
        repo_path = tmp_path / "source"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._configure_git(repo_path)
        self._create_commit(repo_path, "README.md", "# Test")

        pr_id = PullRequestId("test-org/test-repo", 42)
        sut = LocalGitRepository(temp_base_dir=tmp_path / "clones")
        clone_path = sut.clone(pr_id, f"file://{repo_path}")

        self._configure_git(clone_path)
        subprocess.run(
            ["git", "-C", str(clone_path), "checkout", "--orphan", "pr-42"],
            check=True,
            capture_output=True,
            text=True,
        )
        (clone_path / "orphan.txt").write_text("orphan")
        subprocess.run(
            ["git", "-C", str(clone_path), "add", "orphan.txt"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(clone_path), "commit", "-m", "Orphan commit"],
            check=True,
            capture_output=True,
            text=True,
        )

        origin_head_sha = self._get_rev_parse(clone_path, "origin/HEAD")

        resolved = sut.resolve_base_sha(clone_path, 42)

        assert resolved == origin_head_sha

    def test_run_git_nonzero_raises_runtime_error(self, tmp_path: Path) -> None:
        """_run_git raises RuntimeError when git exits with nonzero status."""
        repo_path = tmp_path / "source"
        repo_path.mkdir()
        subprocess.run(
            ["git", "init", "-b", "main", str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._configure_git(repo_path)
        self._create_commit(repo_path, "README.md", "# Test")

        sut = LocalGitRepository(temp_base_dir=tmp_path / "clones")

        try:
            sut._run_git(repo_path, "nonexistent-git-subcommand")
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected RuntimeError was not raised")
