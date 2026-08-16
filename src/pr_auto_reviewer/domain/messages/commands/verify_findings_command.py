"""VerifyFindingsCommand — input for verifying blocking review findings against source code."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pr_auto_reviewer.domain.entities.review_item import ReviewItem


@dataclass(frozen=True)
class VerifyFindingsCommand:
    """Command to verify CRITICAL/MAJOR findings against actual source code.

    The verifier runs a separate agentic conversation that reads files,
    searches for symbols, and confirms or rejects each finding.
    """

    items: list[ReviewItem]
    repo_path: Path
    changed_files: list[str]
