"""LocalGitRepository — implements LocalRepositoryPort via git subprocess calls."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from pr_auto_reviewer.application.ports.outbound.local_repository_port import (
    LocalRepositoryPort,
)
from pr_auto_reviewer.domain.exceptions.repository_fetch_error import (
    RepositoryFetchError,
)
from pr_auto_reviewer.domain.value_objects.clone_protocol import CloneProtocol
from pr_auto_reviewer.domain.value_objects.git_credentials import GitCredentials
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId

logger = logging.getLogger(__name__)


class LocalGitRepository(LocalRepositoryPort):
    """Operates on a locally-cloned git repository using subprocess git."""

    def __init__(
        self,
        temp_base_dir: Path,
        credentials: GitCredentials | None = None,
    ) -> None:
        self._temp_base_dir = temp_base_dir
        self._credentials = credentials
        self._last_clone_path: Path | None = None
        self._pr_refs: dict[Path, str] = {}

    @property
    def credentials(self) -> GitCredentials | None:
        return self._credentials

    @credentials.setter
    def credentials(self, value: GitCredentials | None) -> None:
        self._credentials = value

    @property
    def last_clone_path(self) -> Path | None:
        return self._last_clone_path

    def _ssh_env(self) -> dict[str, str]:
        env = os.environ.copy()
        ssh_opts = "-o BatchMode=yes -o StrictHostKeyChecking=accept-new"
        if self._credentials and self._credentials.protocol == CloneProtocol.SSH:
            ssh_opts = f"{ssh_opts} -l {self._credentials.username}"
        env["GIT_SSH_COMMAND"] = f"ssh {ssh_opts}"
        return env

    def _askpass_script(self) -> Path | None:
        if not (self._credentials and self._credentials.protocol == CloneProtocol.HTTPS):
            return None
        script_path = self._temp_base_dir / "git-askpass.sh"
        if not script_path.exists():
            self._temp_base_dir.mkdir(parents=True, exist_ok=True)
            script_path.write_text(
                "#!/bin/sh\n"
                'case "$1" in\n'
                '*[Uu]sername*) printf "%s\n" "$GIT_CREDENTIAL_USERNAME" ;;\n'
                '*) printf "%s\n" "$GIT_CREDENTIAL_PASSWORD" ;;\n'
                "esac\n"
            )
            script_path.chmod(0o700)
        return script_path

    def _auth_env(self) -> dict[str, str]:
        env = self._ssh_env()
        if self._credentials and self._credentials.protocol == CloneProtocol.HTTPS:
            script_path = self._askpass_script()
            if script_path is not None:
                env["GIT_ASKPASS"] = str(script_path)
                env["GIT_TERMINAL_PROMPT"] = "0"
                env["GIT_CREDENTIAL_USERNAME"] = self._credentials.username
                env["GIT_CREDENTIAL_PASSWORD"] = self._credentials.secret
        return env

    def clone(self, pr_id: PullRequestId, clone_url: str) -> Path:
        dir_name = f"{pr_id.repository.replace('/', '_')}_{pr_id.number}"
        dest = self._temp_base_dir / dir_name

        if dest.exists():
            logger.info("Repository already cloned at %s, updating fetch", dest)
            try:
                self._run_git(dest, "fetch", "--all", "--prune")
            except RuntimeError as exc:
                raise RepositoryFetchError(
                    f"Could not update existing clone at {dest}: {exc}"
                ) from exc
        else:
            logger.info("Cloning %s into %s (full clone for merge-base)", clone_url, dest)
            self._temp_base_dir.mkdir(parents=True, exist_ok=True)
            try:
                subprocess.run(
                    ["git", "clone", clone_url, str(dest)],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=300,
                    env=self._auth_env(),
                )
            except subprocess.CalledProcessError as exc:
                logger.error(
                    "git clone failed for %s: %s", clone_url, exc.stderr.strip()
                )
                raise RepositoryFetchError(
                    f"git clone {clone_url} failed: {exc.stderr.strip()}"
                ) from exc

        pr_ref = f"pull/{pr_id.number}/head"
        pr_branch = f"pr-{pr_id.number}"
        try:
            self._run_git(
                dest,
                "fetch",
                "origin",
                "+" + pr_ref + f":{pr_branch}",
            )
            self._pr_refs[dest] = pr_branch
            self._run_git(dest, "checkout", pr_branch)
        except RuntimeError:
            logger.warning(
                "Could not fetch PR ref %s — PR may be from a fork. "
                "Falling back to diff against origin/HEAD.",
                pr_ref,
            )
        self._last_clone_path = dest
        return dest

    def remove(self, repo_path: Path) -> None:
        self._pr_refs.pop(repo_path, None)
        if repo_path.exists():
            logger.info("Removing cloned repository at %s", repo_path)
            shutil.rmtree(repo_path)
        if self._last_clone_path == repo_path:
            self._last_clone_path = None

    def compute_diff(
        self, repo_path: Path, base_sha: str, head_sha: str,
    ) -> str:
        return self._run_git(repo_path, "diff", f"{base_sha}..{head_sha}")

    def commit_messages(
        self, repo_path: Path, base_sha: str, head_sha: str,
    ) -> list[str]:
        output = self._run_git(
            repo_path,
            "log",
            f"{base_sha}..{head_sha}",
            "--format=%s",
        )
        return [
            line.strip()
            for line in output.split("\n")
            if line.strip()
        ]

    def read_file(self, repo_path: Path, file_path: str, ref: str = "HEAD") -> str:
        effective_ref = self._pr_refs.get(repo_path, ref)
        return self._run_git(repo_path, "show", f"{effective_ref}:{file_path}")

    def list_tree(self, repo_path: Path, ref: str = "HEAD") -> list[str]:
        effective_ref = self._pr_refs.get(repo_path, ref)
        output = self._run_git(repo_path, "ls-tree", "-r", "--name-only", effective_ref)
        return [line for line in output.splitlines() if line.strip()]


    def resolve_base_sha(self, repo_path: Path, pr_number: int) -> str:
        """Determine the merge-base for a PR using the default branch.

        Uses origin/HEAD (the default branch) as the base and computes
        the merge-base with the fetched PR head ref. Falls back to
        origin/HEAD itself if no common ancestor is found.
        """
        head_ref = f"pr-{pr_number}"
        try:
            return self._run_git(
                repo_path,
                "merge-base",
                "origin/HEAD",
                head_ref,
            ).strip()
        except RuntimeError:
            logger.warning(
                "Could not compute merge-base with origin/HEAD. "
                "Using origin/HEAD as base."
            )
            return self._run_git(
                repo_path,
                "rev-parse",
                "origin/HEAD",
            ).strip()

    def _run_git(
        self,
        repo_path: Path,
        *args: str,
        timeout: int = 120,
    ) -> str:
        cmd = ["git", "-C", str(repo_path), *args]
        logger.debug("Running git: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self._auth_env(),
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed: {result.stderr.strip()}"
            )
        return result.stdout
