"""ReviewExecutionContext — shared state for multi-phase reviews."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pr_auto_reviewer.domain.entities.review_item import ReviewItem


@dataclass(frozen=True)
class ReviewExecutionContext:
    """Immutable state shared by the phases of one review execution."""

    repo_path: Path
    changed_files: tuple[str, ...]
    model: str
    review_session: str = ""
    base_sha: str = ""
    existing_item_ids: frozenset[str] = frozenset()
    pr_identifier_service: str = ""
    prior_items: tuple[ReviewItem, ...] = ()
