"""Integration tests for LocalGitRepository — real git operations, no mocks.

These tests require ``git`` on PATH. They are skipped when git is not
installed so they do not break CI/CD runners that lack git.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from pr_auto_reviewer.domain.exceptions.repository_fetch_error import (
    RepositoryFetchError,
)
from pr_auto_reviewer.domain.value_objects.git_credentials import GitCredentials
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.local_repository.local_git_repository import (
    LocalGitRepository,
)

import requests

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.client.remote_host_backoff import (
    RemoteHostBackoff,
)


class _Clock:
    def __init__(self) -> None:
        self.value = 100.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git is not installed on this runner",
)


class TestLocalGitRepository:

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

    def test_https_credentials_set_up_askpass_env(self, tmp_path: Path) -> None:
        sut = LocalGitRepository(
            tmp_path / "clones",
            credentials=GitCredentials(protocol="https", username="alice", secret="tok"),
        )

        env = sut._auth_env()

        assert env["GIT_TERMINAL_PROMPT"] == "0"
        assert env["GIT_CREDENTIAL_USERNAME"] == "alice"
        assert env["GIT_CREDENTIAL_PASSWORD"] == "tok"
        askpass = Path(env["GIT_ASKPASS"])
        assert askpass.exists()
        content = askpass.read_text()
        assert "GIT_CREDENTIAL_USERNAME" in content
        assert "GIT_CREDENTIAL_PASSWORD" in content

    def test_ssh_credentials_embed_username_in_ssh_command(self, tmp_path: Path) -> None:
        sut = LocalGitRepository(
            tmp_path / "clones",
            credentials=GitCredentials(protocol="ssh", username="deploy", secret=""),
        )

        env = sut._auth_env()

        assert "-l deploy" in env["GIT_SSH_COMMAND"]

    def test_no_credentials_yields_plain_env_without_auth_vars(self, tmp_path: Path) -> None:
        sut = LocalGitRepository(tmp_path / "clones")

        env = sut._auth_env()

        assert "GIT_ASKPASS" not in env
        assert "GIT_CREDENTIAL_USERNAME" not in env
        assert "GIT_SSH_COMMAND" in env
        assert "-l " not in env["GIT_SSH_COMMAND"]

    def test_setting_credentials_after_construction_changes_env(self, tmp_path: Path) -> None:
        sut = LocalGitRepository(tmp_path / "clones")

        sut.credentials = GitCredentials(protocol="https", username="eve", secret="pw")

        env = sut._auth_env()
        assert env["GIT_CREDENTIAL_USERNAME"] == "eve"
        assert env["GIT_CREDENTIAL_PASSWORD"] == "pw"

    def test_clone_update_fetch_failure_raises_repository_fetch_error(
        self, tmp_path: Path
    ) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        sut = LocalGitRepository(tmp_path / "clones")
        sut.clone(PullRequestId("owner/repo", 42), str(repo_path))

        def fail_fetch(*args, **kwargs):
            raise RuntimeError("git fetch --all --prune failed: "
                               "git@codeberg.org: Permission denied (publickey).")

        with patch.object(sut, "_run_git", side_effect=fail_fetch), pytest.raises(
            RepositoryFetchError, match="Permission denied"
        ):
            sut.clone(PullRequestId("owner/repo", 42), str(repo_path))

    def test_clone_full_clone_failure_raises_repository_fetch_error(
        self, tmp_path: Path
    ) -> None:
        repo_path = self._init_repo(tmp_path, "source")
        sut = LocalGitRepository(tmp_path / "clones")

        def fail_clone(*args, **kwargs):
            raise subprocess.CalledProcessError(
                returncode=128,
                cmd=["git", "clone", "ssh://git@host/repo.git"],
                stderr="ssh: connect to host port 22: Connection refused",
            )

        with patch.object(sut, "_ssh_env", return_value={}), patch(
            "pr_auto_reviewer.infrastructure.local_repository.local_git_repository.subprocess.run",
            side_effect=fail_clone,
        ), pytest.raises(RepositoryFetchError, match="Connection refused"):
            sut.clone(PullRequestId("owner/repo", 42), str(repo_path))

    def test_clone_timeout_counts_as_repository_fetch_failure(
        self, tmp_path: Path,
    ) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(
            threshold=4, clock=clock.now, sleeper=clock.sleep,
        )
        sut = LocalGitRepository(
            tmp_path / "clones",
            remote_host_backoff=backoff,
        )

        def fail_clone(*args, **kwargs):
            raise subprocess.TimeoutExpired(["git", "clone"], timeout=300)

        with patch(
            "pr_auto_reviewer.infrastructure.local_repository.local_git_repository.subprocess.run",
            side_effect=fail_clone,
        ):
            for _ in range(4):
                with pytest.raises(RepositoryFetchError, match="timed out"):
                    sut.clone(
                        PullRequestId("owner/repo", 42),
                        "git@codeberg.org:owner/repo.git",
                    )

        assert clock.sleeps == [60.0, 120.0, 180.0]

    def test_existing_clone_fetch_timeout_counts_as_repository_fetch_failure(

        self, tmp_path: Path,
    ) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(
            threshold=4, clock=clock.now, sleeper=clock.sleep,
        )
        sut = LocalGitRepository(
            tmp_path / "clones",
            remote_host_backoff=backoff,
        )
        clone_path = tmp_path / "clones" / "owner_repo_42"
        clone_path.mkdir(parents=True)

        def fail_fetch(*args, **kwargs):
            raise subprocess.TimeoutExpired(["git", "fetch"], timeout=120)

        with patch.object(sut, "_run_git", side_effect=fail_fetch):
            for _ in range(4):
                with pytest.raises(RepositoryFetchError, match="timed out"):
                    sut.clone(
                        PullRequestId("owner/repo", 42),
                        "git@codeberg.org:owner/repo.git",
                    )

        assert clock.sleeps == [60.0, 120.0, 180.0]
    def test_pr_ref_fetch_timeout_records_backoff_and_falls_back(
        self, tmp_path: Path,
    ) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(
        threshold=2,
            clock=clock.now,
            sleeper=clock.sleep,
        )
        sut = LocalGitRepository(
            tmp_path / "clones",
            remote_host_backoff=backoff,
        )

        def fake_clone(args, **kwargs):
            Path(args[-1]).mkdir(parents=True)

        def timeout_fetch(*args, **kwargs):
            raise subprocess.TimeoutExpired(["git", "fetch"], timeout=120)

        with patch(
            "pr_auto_reviewer.infrastructure.local_repository.local_git_repository.subprocess.run",
            side_effect=fake_clone,
        ), patch.object(sut, "_run_git", side_effect=timeout_fetch):
            clone_path = sut.clone(
                PullRequestId("owner/repo", 42),
                "git@codeberg.org:owner/repo.git",
            )

        assert clone_path == tmp_path / "clones" / "owner_repo_42"
        assert clone_path.exists()
        backoff.before_operation("codeberg.org")
        assert clock.sleeps == [60.0]


    def test_ssh_clone_failures_share_backoff_with_api_requests(
        self, tmp_path: Path, monkeypatch,
    ) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(
            threshold=4, clock=clock.now, sleeper=clock.sleep,
        )
        sut = LocalGitRepository(
            tmp_path / "clones",
            remote_host_backoff=backoff,
        )

        def fail_clone(*args, **kwargs):
            raise subprocess.CalledProcessError(
                returncode=128,
                cmd=["git", "clone", "git@codeberg.org:owner/repo.git"],
                stderr="Permission denied (publickey)",
            )

        with patch(
            "pr_auto_reviewer.infrastructure.local_repository.local_git_repository.subprocess.run",
            side_effect=fail_clone,
        ):
            for _ in range(2):
                with pytest.raises(RepositoryFetchError):
                    sut.clone(
                        PullRequestId("owner/repo", 42),
                        "git@codeberg.org:owner/repo.git",
                    )

        def fail_api(*args, **kwargs):
            raise requests.ConnectionError("connection refused")

        monkeypatch.setattr(requests, "get", fail_api)
        client = GitPlatformHttpClient(
            "https://codeberg.org/api/v1",
            "token",
            remote_host_backoff=backoff,
        )
        with pytest.raises(requests.ConnectionError):
            client.get("/user")

        response = requests.Response()
        response.status_code = 200
        response._content = b"{}"
        monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)
        client.get("/user")

        assert clock.sleeps == [60.0, 120.0, 180.0]

    def test_list_tree_returns_file_list(self, tmp_path: Path) -> None:
        """list_tree returns the list of tracked files at a ref."""
        repo_path = self._init_repo(tmp_path, "source")
        (repo_path / "src").mkdir()
        self._create_commit(repo_path, "src/main.py", "print('hello')")
        sut = LocalGitRepository(tmp_path / "clones")
        files = sut.list_tree(repo_path, ref="HEAD")

        assert "README.md" in files
        assert "src/main.py" in files
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
