"""PullRequestDiff — immutable snapshot of what changed in a PR at a specific commit."""

from dataclasses import dataclass, field
from pathlib import Path

from .commit_sha import CommitSha
from .pull_request_id import PullRequestId


@dataclass(frozen=True)
class PullRequestDiff:
    """Immutable snapshot of what changed in a PR at a specific commit."""

    pr_id: PullRequestId
    head_sha: CommitSha
    diff_content: str
    file_contents: dict[str, str] = field(default_factory=dict)
    repository_structure: str | None = None
    conventions: str | None = None
    commit_messages: list[str] = field(default_factory=list)
    clone_path: Path | None = None
