"""General settings presentation port."""

from __future__ import annotations

from typing import Protocol

from pr_auto_reviewer.presentation.cli.settings_cli import SettingsSnapshot


class GeneralSettingsPort(Protocol):
    """Read and write non-credential settings."""

    def snapshot(self) -> SettingsSnapshot:
        """Return visible settings and secret names."""
        ...

    def write(self, name: str, raw_value: str) -> None:
        """Write a setting without returning its value."""
        ...

    def unset(self, name: str) -> None:
        """Remove a setting."""
        ...
