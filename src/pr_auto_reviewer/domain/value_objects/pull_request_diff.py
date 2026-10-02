"""PullRequestDiff — immutable snapshot of what changed in a PR at a specific commit."""

from dataclasses import dataclass, field
import re
from pathlib import Path

from .commit_sha import CommitSha
from .pull_request_id import PullRequestId

_DIFF_FILE_PATH_RE = re.compile(
    r"^\s*diff --git a/(.+?)\s+b/(.+?)$", re.MULTILINE
)


@dataclass(frozen=True)
class PullRequestDiff:
    """Immutable snapshot of what changed in a PR at a specific commit."""

    pr_id: PullRequestId
    head_sha: CommitSha
    diff_content: str
    base_sha: CommitSha | None = None
    file_contents: dict[str, str] = field(default_factory=dict)
    repository_structure: str | None = None
    conventions: str | None = None
    commit_messages: list[str] = field(default_factory=list)
    clone_path: Path | None = None

    @property
    def changed_paths(self) -> list[str]:
        """Sorted, deduplicated paths from the diff's file headers."""
        return sorted({
            match.group(2)
            for match in _DIFF_FILE_PATH_RE.finditer(self.diff_content)
            if match.group(2) != "/dev/null"
        })
