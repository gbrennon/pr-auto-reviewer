"""LocalRepositoryPort — protocol for local git repository operations."""

from pathlib import Path
from typing import Protocol

from ....domain.value_objects.pull_request_id import PullRequestId


class LocalRepositoryPort(Protocol):
    """Operations on a locally-cloned git repository.

    Used by LocalChangesetFetcher to compute diffs and read file
    contents from a local clone instead of HTTP API calls.
    """

    def clone(self, pr_id: PullRequestId, clone_url: str) -> Path:
        """Clone the repository and fetch the PR ref. Idempotent.

        Returns the path to the cloned repository.
        """
        ...

    def remove(self, repo_path: Path) -> None:
        """Remove the cloned repository directory."""
        ...

    def compute_diff(
        self, repo_path: Path, base_sha: str, head_sha: str,
    ) -> str:
        """Compute the unified diff between two commits."""
        ...

    def commit_messages(
        self, repo_path: Path, base_sha: str, head_sha: str,
    ) -> list[str]:
        """Return commit messages between two commits."""
        ...
    def resolve_base_sha(self, repo_path: Path, pr_number: int) -> str:
        """Determine the merge-base for a PR against the default branch."""
        ...

    def read_file(
        self, repo_path: Path, file_path: str, ref: str = "HEAD",
    ) -> str:
        """Read the full contents of a file at a given ref."""
        ...

    def list_tree(
        self, repo_path: Path, ref: str = "HEAD",
    ) -> list[str]:
        """List all files tracked at a given ref.

        Returns a list of relative file paths.
        """
        ...


    @property
    def last_clone_path(self) -> Path | None:
        """The path of the most recent clone, or None."""
        ...
