"""TOML persistence for non-secret application settings."""

from __future__ import annotations

import json
import os
import tempfile
import tomllib
from pathlib import Path
from typing import TypeAlias

TomlValue: TypeAlias = str | int | float | bool | list[object] | dict[str, object]

_SECRET_KEY_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "KEY")


class TomlSettingsStore:
    """Read and atomically write typed settings in a flat TOML document."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @staticmethod
    def is_secret_name(name: str) -> bool:
        """Return whether a setting name denotes a secret credential."""
        normalized = name.upper()
        return any(marker in normalized for marker in _SECRET_KEY_MARKERS)

    def get(self, name: str, default: TomlValue | None = None) -> TomlValue | None:
        """Return one setting without exposing secret values."""
        return self.all().get(name, default)

    def all(self) -> dict[str, TomlValue]:
        """Return all persisted non-secret settings."""
        try:
            with self._path.open("rb") as stream:
                values = tomllib.load(stream)
        except FileNotFoundError:
            return {}
        return values

    def set(self, name: str, value: TomlValue) -> None:
        """Create or replace a setting and persist the complete document."""
        self._validate_name(name)
        values = self.all()
        values[name] = value
        self._write(values)

    def delete(self, name: str) -> None:
        """Delete a setting when present."""
        values = self.all()
        values.pop(name, None)
        self._write(values)

    def _validate_name(self, name: str) -> None:
        normalized = name.upper()
        if self.is_secret_name(name):
            raise ValueError("secret settings must be stored in encrypted persistence")
        if not name or any(character in name for character in " \t\n="):
            raise ValueError("Setting name must be a non-empty TOML key")

    def _write(self, values: dict[str, TomlValue]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(
            prefix=f"{self._path.name}.", suffix=".tmp", dir=self._path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                for name, value in sorted(values.items()):
                    stream.write(f"{name} = {json.dumps(value, ensure_ascii=False)}\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self._path)
        except BaseException:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
            raise
