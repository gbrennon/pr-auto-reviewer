"""LocalRepositoryContext — uses local git clone to implement RepositoryContextPort."""

from __future__ import annotations

import logging
import subprocess

from pr_auto_reviewer.application.ports.outbound.local_repository_port import (
    LocalRepositoryPort,
)
from pr_auto_reviewer.application.ports.outbound.repository_context_port import (
    RepositoryContextPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.context.architecture_detector import (
    ArchitectureDetector,
)
from pr_auto_reviewer.infrastructure.context.context_serializer import ContextSerializer
from pr_auto_reviewer.infrastructure.context.language_detector import LanguageDetector
from pr_auto_reviewer.infrastructure.context.python_version_detector import (
    PythonVersionDetector,
)

logger = logging.getLogger(__name__)

_CONVENTIONS_FILENAMES = ("ARCHITECTURE.md", "CONVENTIONS.md", ".architecturerc")


class LocalRepositoryContext(RepositoryContextPort):
    """Fetches repository structure, architecture hint, and conventions
    from a local git clone.

    Composes ArchitectureDetector, LanguageDetector, and
    ContextSerializer collaborators instead of inline private
    methods.
    """

    def __init__(self, local_repository: LocalRepositoryPort) -> None:
        self._local_repository = local_repository
        self._architecture_detector = ArchitectureDetector()
        self._language_detector = LanguageDetector()
        self._context_serializer = ContextSerializer()
        self._python_version_detector = PythonVersionDetector()

    def fetch(self, pr_id: PullRequestId, target_branch: str = "") -> RepositoryContext:
        """Return RepositoryContext for the given PR's repository."""
        logger.info("RepositoryContext.fetch(%s)", pr_id)
        architecture_hint = "unknown"
        repository_structure: str | None = None

        repo_path = self._local_repository.last_clone_path
        if repo_path is None:
            logger.warning("No clone path available for %s, using defaults", pr_id)
            return RepositoryContext(
                architecture_hint=architecture_hint,
                conventions=None,
                repository_structure=repository_structure,
                python_version=None,
            )

        tree_paths: list[str] = []
        try:
            tree_paths = self._local_repository.list_tree(
                repo_path, ref=target_branch or "HEAD",
            )
            repository_structure = "\n".join(tree_paths)
            architecture_hint = self._architecture_detector.detect(tree_paths)
        except (RuntimeError, subprocess.TimeoutExpired):
            logger.warning(
                "Failed to list tree for %s, using defaults", pr_id, exc_info=True,
            )

        conventions: str | None = None
        for filename in _CONVENTIONS_FILENAMES:
            if filename not in tree_paths:
                continue
            try:
                conventions = self._local_repository.read_file(
                    repo_path, filename, ref=target_branch or "HEAD",
                )
                break
            except (RuntimeError, subprocess.TimeoutExpired):
                logger.debug(
                    "Failed to read %s from %s", filename, pr_id, exc_info=True,
                )
                continue

        python_version = self._python_version_detector.detect(tree_paths)

        repo_ctx = RepositoryContext(
            architecture_hint=architecture_hint,
            conventions=conventions,
            repository_structure=repository_structure,
            python_version=python_version,
        )
        logger.info(
            "RepositoryContext.fetch return: arch=%s conventions=%s structure=%s python=%s",
            repo_ctx.architecture_hint,
            f"{len(repo_ctx.conventions)} chars" if repo_ctx.conventions else "none",
            f"{len(repo_ctx.repository_structure)} chars" if repo_ctx.repository_structure else "none",
            repo_ctx.python_version,
        )
        return repo_ctx

    def build_fragment_context(
        self,
        repo_context: RepositoryContext,
        file_paths: list[str],
        commit_messages: list[str] | None = None,
    ) -> tuple[str, str | None]:
        """Detect language and serialise context + commit messages.

        Returns (language, serialized_context).
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
