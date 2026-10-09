"""AuditRemediationCommand — input for auditing prior findings on changed files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.review_item_lifecycle import (
    ReviewItemLifecycle,
)


@dataclass(frozen=True)
class AuditRemediationCommand:
    """Audit historical items and suggestions against the current commit."""

    prior_items: list[ReviewItem]
    repo_path: Path
    changed_files: list[str]
    review_session: str
    base_sha: str = ""
    prior_suggestions: list[ReviewItem] = field(default_factory=list)
    prior_lifecycles: tuple[ReviewItemLifecycle, ...] = ()
    current_sha: str = ""
