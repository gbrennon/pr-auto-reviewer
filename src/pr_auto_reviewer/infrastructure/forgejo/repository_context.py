"""ForgejoRepositoryContext — wraps GitPlatformHttpClient to implement RepositoryContextPort."""

from __future__ import annotations

import logging

from pr_auto_reviewer.application.ports.outbound.repository_context_port import (
    RepositoryContextPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)

from pr_auto_reviewer.infrastructure.context.architecture_detector import ArchitectureDetector
from pr_auto_reviewer.infrastructure.context.context_serializer import ContextSerializer
from pr_auto_reviewer.infrastructure.context.language_detector import LanguageDetector
from pr_auto_reviewer.infrastructure.context.python_version_detector import PythonVersionDetector

logger = logging.getLogger(__name__)

_CONVENTIONS_FILENAMES = ("ARCHITECTURE.md", "CONVENTIONS.md", ".architecturerc")

class ForgejoRepositoryContext(RepositoryContextPort):
    """Fetches repository structure, architecture hint, and conventions.

    Composes ``ArchitectureDetector``, ``LanguageDetector``, and
    ``ContextSerializer`` collaborators instead of inline private
    methods.
    """

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client
        self._architecture_detector = ArchitectureDetector()
        self._language_detector = LanguageDetector()
        self._context_serializer = ContextSerializer()
        self._python_version_detector = PythonVersionDetector()

    def fetch(self, pr_id: PullRequestId) -> RepositoryContext:
        """Return RepositoryContext for the given PR's repository."""
        logger.info("RepositoryContext.fetch(%s)", pr_id)
        architecture_hint = "unknown"
        repository_structure: str | None = None

        tree_paths: list[str] = []
        tree_path = f"/repos/{pr_id.repository}/git/trees/main?recursive=1"
        try:
            response = self._client.get(tree_path, repo=pr_id.repository)
            tree_blobs = response.get("tree", [])
            tree_paths = [entry["path"] for entry in tree_blobs]
            repository_structure = "\n".join(tree_paths)

            architecture_hint = self._architecture_detector.detect(tree_paths)
        except Exception:
            logger.warning(
                "Failed to fetch git tree for %s, using defaults", pr_id
            )

        conventions: str | None = None
        for filename in _CONVENTIONS_FILENAMES:
            if filename not in tree_paths:
                continue
            try:
                raw_path = f"/repos/{pr_id.repository}/raw/main/{filename}"
                conventions = self._client.get_raw(raw_path, repo=pr_id.repository)
                break
            except Exception:
                continue

        python_version = self._python_version_detector.detect(tree_paths)

        repo_ctx = RepositoryContext(
            architecture_hint=architecture_hint,
            conventions=conventions,
            repository_structure=repository_structure,
            python_version=python_version,
        )
        logger.info(
            "RepositoryContext.fetch return: arch=%s conventions=%s structure=%d lines python=%s",
            architecture_hint,
            f"{len(conventions)} chars" if conventions else "none",
            len(tree_paths),
            python_version or "none",
        )
        return repo_ctx

    def build_fragment_context(
        self,
        repo_context: RepositoryContext,
        file_paths: list[str],
        commit_messages: list[str] | None = None,
    ) -> tuple[str, str | None]:
        """Detect language and serialise context + commit messages.

        Returns ``(language, serialized_context)``.
        """
        logger.info(
            "RepositoryContext.build_fragment_context(files=%d, commits=%s)",
            len(file_paths), len(commit_messages) if commit_messages else 0,
        )
        language = self._language_detector.detect(file_paths)

        version = repo_context.python_version
        if version is None and language == "python":
            version = "3.9"

        serialized = self._context_serializer.serialize(
            repo_context, commit_messages,
            python_version=self._python_version_detector.guidance(version),
        )
        logger.info(
            "build_fragment_context return: language=%s serialized=%s",
            language, f"{len(serialized)} chars" if serialized else "none",
        )
        return language, serialized
