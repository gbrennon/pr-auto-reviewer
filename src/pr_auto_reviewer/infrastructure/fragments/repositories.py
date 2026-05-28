"""FileSystemFragmentRepository — loads prompt fragments from disk."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from pr_auto_reviewer.domain.fragments.entities.prompt_fragment import PromptFragment

logger = logging.getLogger(__name__)


class FileSystemFragmentRepository:
    """Loads prompt fragments from YAML-front-matter Markdown files on disk.

    Directory structure expected::

        base_path/
            python/
                error-handling.md
                idioms.md
            go/
                concurrency.md
            universal/
                solid-principles.md

    Each ``.md`` file must begin with YAML front matter delimited by
    ``---`` lines.  The YAML block must contain at minimum an ``id``
    field.  Optional fields: ``language``, ``priority``, ``category``,
    and any additional metadata keys.

    Malformed or incomplete files are silently skipped — they never
    cause the repository to crash.
    """

    def __init__(self, base_path: Path) -> None:
        """Initialise the repository.

        Args:
            base_path: Root directory containing per-language
                sub-directories and a ``universal/`` directory.

        Raises:
            ValueError: If *base_path* does not exist or is not a
                directory.
        """
        if not base_path.exists():
            raise ValueError(f"base_path does not exist: {base_path}")
        if not base_path.is_dir():
            raise ValueError(f"base_path must be a directory: {base_path}")

        self.base_path = base_path

    def find_by_language(self, language: str) -> list[PromptFragment]:
        """Return all fragments for *language*, sorted by priority descending.

        Returns an empty list when the language directory is missing.
        """
        language_dir = self.base_path / language

        if not language_dir.is_dir():
            return []

        fragments: list[PromptFragment] = []
        for md_file in sorted(language_dir.glob("*.md")):
            fragment = self._load_fragment(md_file)
            if fragment is not None:
                fragments.append(fragment)

        fragments.sort(key=lambda f: f.priority, reverse=True)
        return fragments

    def find_universal(self) -> list[PromptFragment]:
        """Return all universal (language-agnostic) fragments."""
        universal_dir = self.base_path / "universal"

        if not universal_dir.is_dir():
            return []

        fragments: list[PromptFragment] = []
        for md_file in sorted(universal_dir.glob("*.md")):
            fragment = self._load_fragment(md_file)
            if fragment is not None and fragment.is_universal():
                fragments.append(fragment)

        fragments.sort(key=lambda f: f.priority, reverse=True)
        return fragments

    def find_by_id(self, fragment_id: str) -> PromptFragment | None:
        """Return a single fragment by its unique ID, or ``None``.

        Searches across all language directories *and* ``universal/``.
        """
        for subdir in sorted(self.base_path.iterdir()):
            if not subdir.is_dir():
                continue

            for md_file in sorted(subdir.glob("*.md")):
                fragment = self._load_fragment(md_file)
                if fragment is not None and fragment.id == fragment_id:
                    return fragment

        return None

    @staticmethod
    def _load_fragment(file_path: Path) -> PromptFragment | None:
        """Parse a single ``.md`` file into a :class:`PromptFragment`.

        Returns ``None`` for any file that is malformed, missing
        required front-matter fields, or otherwise unparseable — the
        caller is responsible for skipping these gracefully.
        """
        try:
            raw = file_path.read_text()
        except OSError:
            logger.warning("Cannot read fragment file: %s", file_path)
            return None

        # Must start with YAML front matter
        if not raw.startswith("---"):
            return None

        parts = raw.split("---", 2)
        if len(parts) < 3:
            return None

        front_matter_raw = parts[1]
        markdown_content = parts[2].strip()

        try:
            front_matter: dict = yaml.safe_load(front_matter_raw)
        except yaml.YAMLError:
            logger.warning("Malformed YAML in fragment: %s", file_path)
            return None

        if not isinstance(front_matter, dict):
            return None

        fragment_id = front_matter.get("id")

        if not fragment_id or not str(fragment_id).strip():
            logger.warning("Fragment missing 'id' field: %s", file_path)
            return None

        try:
            return PromptFragment(
                id=str(fragment_id),
                content=markdown_content,
                language=front_matter.get("language"),
                priority=int(front_matter.get("priority", 50)),
                category=str(front_matter.get("category", "general")),
                metadata=front_matter,
            )
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Invalid fragment data in %s: %s", file_path, exc,
            )
            return None
