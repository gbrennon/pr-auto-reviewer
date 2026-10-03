"""VerifyFindingsCommand — input for verifying blocking review findings against source code."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pr_auto_reviewer.domain.entities.review_item import ReviewItem


@dataclass(frozen=True)
class VerifyFindingsCommand:
    """Command to verify CRITICAL/MAJOR findings against actual source code."""

    items: list[ReviewItem]
    repo_path: Path
    changed_files: list[str]
    review_session: str
    """Opaque review-run key (start timestamp) grouping transcripts for one run."""
    base_sha: str = ""
    """PR merge-base against the default branch; scopes the verifier's git reads."""
