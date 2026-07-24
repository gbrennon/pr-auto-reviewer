"""LocalGitRepository — implements LocalRepositoryPort via git subprocess calls."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from pr_auto_reviewer.application.ports.outbound.local_repository_port import (
    LocalRepositoryPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId

logger = logging.getLogger(__name__)


class LocalGitRepository(LocalRepositoryPort):
    """Operates on a locally-cloned git repository using subprocess git."""

    def __init__(self, temp_base_dir: Path) -> None:
        self._temp_base_dir = temp_base_dir
        self._last_clone_path: Path | None = None
        self._pr_refs: dict[Path, str] = {}

    @property
    def last_clone_path(self) -> Path | None:
        return self._last_clone_path

    def clone(self, pr_id: PullRequestId, clone_url: str) -> Path:
        dir_name = f"{pr_id.repository.replace('/', '_')}_{pr_id.number}"
        dest = self._temp_base_dir / dir_name

        if dest.exists():
            logger.info("Repository already cloned at %s, updating fetch", dest)
            self._run_git(dest, "fetch", "--all", "--prune")
        else:
            logger.info("Cloning %s into %s (full clone for merge-base)", clone_url, dest)
            self._temp_base_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", clone_url, str(dest)],
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )

        pr_ref = f"pull/{pr_id.number}/head"
        try:
            self._run_git(
                dest,
                "fetch",
                "origin",
                "+" + pr_ref + f":pr-{pr_id.number}",
            )
            self._pr_refs[dest] = f"pr-{pr_id.number}"
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
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed: {result.stderr.strip()}"
            )
        return result.stdout
