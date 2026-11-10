from __future__ import annotations

from pathlib import Path

import pr_auto_reviewer


class TestPackageRootPurity:
    """Verifies that the package root contains only dunder files and layer packages."""

    @staticmethod
    def _is_dunder_file(name: str) -> bool:
        return name.startswith("__") and name.endswith("__.py")

    def test_package_root_contains_only_dunder_files(self) -> None:
        root_dir = Path(pr_auto_reviewer.__file__).parent
        file_entries = [
            item.name for item in root_dir.iterdir()
            if item.is_file()
        ]

        non_dunder_files = [
            name for name in file_entries
            if not self._is_dunder_file(name)
        ]

        assert non_dunder_files == []

    def test_package_root_directories_match_architecture_layers(self) -> None:
        root_dir = Path(pr_auto_reviewer.__file__).parent
        dir_entries = {
            item.name for item in root_dir.iterdir()
            if item.is_dir() and not item.name.startswith((".", "__"))
        }

        assert dir_entries == {
            "domain",
            "application",
            "infrastructure",
            "presentation",
        }
