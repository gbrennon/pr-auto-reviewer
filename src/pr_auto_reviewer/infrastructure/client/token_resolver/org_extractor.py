"""Extracts the organisation name from repository paths."""

from __future__ import annotations


class OrgExtractor:
    """Extracts the organisation name from repository paths."""

    @classmethod
    def from_repo(cls, repo: str) -> str:
        """Return the org portion of ``"org/repo"``, or ``""``."""
        if "/" in repo:
            return repo.split("/", 1)[0]
        return ""
