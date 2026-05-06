"""GitRepositoryContextAdapter — wraps GitPlatformHttpClient to implement RepositoryContextPort."""

from __future__ import annotations

import logging

from pr_auto_reviewer.application.ports.outbound.repository_context_port import (
    RepositoryContextPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_context import ReviewContext
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)

from .architecture_detector import ArchitectureDetector

logger = logging.getLogger(__name__)

_CONVENTIONS_FILENAMES = ("ARCHITECTURE.md", "CONVENTIONS.md", ".architecturerc")


class GitRepositoryContextAdapter(RepositoryContextPort):
    """Fetches repository structure, architecture hint, and conventions."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client
        self._detector = ArchitectureDetector()

    # ------------------------------------------------------------------ [port]
    def fetch(self, pr_id: PullRequestId) -> ReviewContext:
        """Return ReviewContext for the given PR's repository."""
        architecture_hint = "unknown"
        repository_structure: str | None = None

        # -- [http] GET git tree (recursive) ---------------------------------
        tree_path = f"/repos/{pr_id.repository}/git/trees/main?recursive=1"
        try:
            response = self._client.get(tree_path)
            tree_blobs = response.get("tree", [])
            tree_paths: list[str] = [entry["path"] for entry in tree_blobs]
            repository_structure = "\n".join(tree_paths)

            # -- [map] detect architecture from tree paths -------------------
            architecture_hint = self._detector.detect(tree_paths)
        except Exception:
            logger.warning(
                "Failed to fetch git tree for %s, using defaults", pr_id
            )

        # -- [http] fetch conventions file (first match wins) ----------------
        conventions: str | None = None
        for filename in _CONVENTIONS_FILENAMES:
            try:
                raw_path = f"/repos/{pr_id.repository}/raw/main/{filename}"
                conventions = self._client.get_raw(raw_path)
                break  # found one
            except Exception:
                continue  # try next filename

        # -- [map] build ReviewContext domain value-object -------------------
        return ReviewContext(
            architecture_hint=architecture_hint,
            conventions=conventions,
            repository_structure=repository_structure,
        )
