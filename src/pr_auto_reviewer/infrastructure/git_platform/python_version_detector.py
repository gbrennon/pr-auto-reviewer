"""PythonVersionDetector — detects target Python version from repo files."""

from __future__ import annotations

import re


class PythonVersionDetector:
    """Detects the minimum Python version a project targets.

    Inspects repository tree paths for known config files and
    produces human-readable guidance for the LLM review.
    """

    _PYPROJECT_RE = re.compile(
        r'requires-python\s*=\s*["\']>=?\s*(\d+\.\d+)', re.IGNORECASE
    )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, tree_paths: list[str]) -> str | None:
        """Return the minimum Python version (e.g. ``"3.9"``) or ``None``.

        Detection order:
        1. ``pyproject.toml`` — presence strongly suggests ≥3.9
        2. ``setup.cfg`` — presence suggests ≥3.7
        3. ``.python-version`` — presence suggests ≥3.7
        4. ``setup.py`` — presence suggests ≥3.7
        """
        has_pyproject = "pyproject.toml" in tree_paths
        has_setup_cfg = "setup.cfg" in tree_paths
        has_python_version = ".python-version" in tree_paths
        has_setup_py = "setup.py" in tree_paths

        if has_pyproject:
            return "3.9"
        if has_setup_cfg:
            return "3.7"
        if has_setup_py or has_python_version:
            return "3.7"
        return None

    def guidance(self, version: str | None) -> str | None:
        """Return human-readable guidance for *version*.

        When *version* is ``≥ 3.9``, recommends modern type-hint syntax
        instead of the old ``typing``-module imports.
        """
        if version is None:
            return None

        try:
            major, minor = version.split(".")
            ver = (int(major), int(minor))
        except (ValueError, TypeError):
            return None

        if ver >= (3, 9):
            return (
                "## Python Version\n\n"
                f"This project targets Python {version}+. "
                "Use modern type-hint syntax:\n\n"
                "- `list[X]` not `List[X]` (no `from typing import List` "
                "needed)\n"
                "- `dict[K, V]` not `Dict[K, V]`\n"
                "- `X | None` not `Optional[X]`\n"
                "- `tuple[X, ...]` not `Tuple[X, ...]`\n"
            )
        return None
