"""SuggestionScopePolicy — deterministic evidence checks for suggestion targets."""

import re
from pathlib import Path


class SuggestionScopePolicy:
    """Validate suggestion targets against the PR's changed-file evidence.

    Enforces minimum textual evidence without attempting semantic dependency
    analysis.
    """

    @classmethod
    def keep(
        cls,
        file_path: str,
        description: str,
        changed_files: list[str],
        normalized_path: str | None,
    ) -> bool:
        """Return whether a suggestion has a safe and evidenced target."""
        cited_path = file_path.strip()
        if not cited_path:
            return True
        if not normalized_path or not normalized_path.strip():
            return False

        changed_paths = cls._normalized_paths(changed_files)
        normalized = cls._normalize_path(normalized_path)
        if normalized in changed_paths:
            return True
        return cls._mentions_changed_path(description, changed_paths)

    @classmethod
    def _normalized_paths(cls, paths: list[str]) -> set[str]:
        return {
            cls._normalize_path(path)
            for path in paths
            if path.strip()
        }

    @staticmethod
    def _normalize_path(path: str) -> str:
        cleaned = path.strip().replace("\\", "/")
        if cleaned.startswith(("a/", "b/")):
            cleaned = cleaned[2:]
        return Path(cleaned).as_posix()

    @classmethod
    def _mentions_changed_path(
        cls, description: str, changed_paths: set[str],
    ) -> bool:
        text = description.casefold()
        basenames: dict[str, list[str]] = {}
        for path in changed_paths:
            basename = path.rsplit("/", 1)[-1].casefold()
            basenames.setdefault(basename, []).append(path)

        for path in changed_paths:
            if cls._contains_name(text, path.casefold()):
                return True
            basename = path.rsplit("/", 1)[-1].casefold()
            if len(basenames[basename]) == 1 and cls._contains_name(text, basename):
                return True
        return False

    @staticmethod
    def _contains_name(text: str, name: str) -> bool:
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])"
        return re.search(pattern, text) is not None
