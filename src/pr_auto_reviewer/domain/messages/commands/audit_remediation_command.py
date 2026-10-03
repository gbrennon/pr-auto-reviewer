"""AuditRemediationCommand — input for auditing prior findings on changed files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pr_auto_reviewer.domain.entities.review_item import ReviewItem


@dataclass(frozen=True)
class AuditRemediationCommand:
    """Command to decide open/resolved for prior findings with proof."""

    prior_items: list[ReviewItem]
    repo_path: Path
    changed_files: list[str]
    review_session: str
    base_sha: str = ""
