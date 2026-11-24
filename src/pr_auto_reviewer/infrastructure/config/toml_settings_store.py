"""TOML persistence for grouped non-secret application settings."""

from __future__ import annotations

import json
import os
import re
import tempfile
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO, TypeAlias, cast

from pr_auto_reviewer.infrastructure.config.settings_key_mapping import (
    aliases_for,
    canonical_settings,
    setting_key,
)

TomlValue: TypeAlias = str | int | float | bool | list[object] | dict[str, object]

_SECRET_SETTING_NAMES = frozenset({
    "GITHUB_MANAGER_TOKEN",
    "GITHUB_REVIEWER_TOKEN",
    "GITHUB_REVIEWER_USERNAME",
    "FORGEJO_MANAGER_TOKEN",
    "FORGEJO_REVIEWER_TOKEN",
    "FORGEJO_REVIEWER_USERNAME",
    "PR_AUTO_REVIEWER_ENCRYPTION_KEY",
})
_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


class TomlSettingsStore:
    """Read grouped settings while accepting legacy flat TOML keys."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @staticmethod
    def is_secret_name(name: str) -> bool:
        """Return whether a setting name denotes a credential."""
        normalized = name.upper()
        return normalized in _SECRET_SETTING_NAMES or normalized.startswith(
            ("GITHUB_TOKEN_", "FORGEJO_TOKEN_")
        )

    def get(self, name: str, default: TomlValue | None = None) -> TomlValue | None:
        """Return one setting using either a grouped or legacy name."""
        key = setting_key(name)
        values = self.all()
        lookup = key.canonical_name if key else name
        return values.get(lookup, default)

    def all(self) -> dict[str, TomlValue]:
        """Return non-secret settings using canonical dotted names."""
        values = canonical_settings(self._document())
        return {
            name: cast(TomlValue, value)
            for name, value in values.items()
            if not self.is_secret_name(name)
        }

    def _document(self) -> dict[str, object]:
        """Return the complete TOML document, including auth tables."""
        try:
            with self._path.open("rb") as stream:
                values = tomllib.load(stream)
        except FileNotFoundError:
            return {}
        return values

    def set(self, name: str, value: TomlValue) -> None:
        """Create or replace a setting in its canonical grouped section."""
        self._validate_name(name)
        document = self._document()
        key = setting_key(name)
        if key is None:
            document[name] = value
        else:
            self._remove_root_aliases(document, key.legacy_name, aliases_for(key))
            self._set_path(document, key.path, value)
        self._write(document)

    def delete(self, name: str) -> None:
        """Delete a setting when present without touching structured tables."""
        document = self._document()
        key = setting_key(name)
        if key is None:
            document.pop(name, None)
        else:
            self._remove_root_aliases(document, key.legacy_name, aliases_for(key))
            self._delete_path(document, key.path)
        self._write(document)

    def _validate_name(self, name: str) -> None:
        if self.is_secret_name(name):
            raise ValueError("secret settings must be stored in encrypted persistence")
        if not name or any(character in name for character in " \t\n="):
            raise ValueError("Setting name must be a non-empty TOML key")

    @staticmethod
    def _remove_root_aliases(
        document: dict[str, object], canonical: str, aliases: tuple[str, ...]
    ) -> None:
        names = {canonical.casefold(), *(alias.casefold() for alias in aliases)}
        for name in tuple(document):
            if name.casefold() in names and not isinstance(document[name], Mapping):
                del document[name]

    @staticmethod
    def _set_path(document: dict[str, object], path: tuple[str, ...], value: object) -> None:
        current = document
        for part in path[:-1]:
            nested = current.get(part)
            if not isinstance(nested, dict):
                nested = {}
                current[part] = nested
            current = nested
        current[path[-1]] = value

    @staticmethod
    def _delete_path(document: dict[str, object], path: tuple[str, ...]) -> None:
        current: dict[str, object] = document
        parents: list[tuple[dict[str, object], str]] = []
        for part in path[:-1]:
            nested = current.get(part)
            if not isinstance(nested, dict):
                return
            parents.append((current, part))
            current = nested
        current.pop(path[-1], None)
        for parent, part in reversed(parents):
            nested = parent.get(part)
            if isinstance(nested, dict) and not nested:
                parent.pop(part, None)

    def _write(self, values: dict[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(
            prefix=f"{self._path.name}.", suffix=".tmp", dir=self._path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                self._write_table(stream, (), values)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self._path)
        except BaseException:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
            raise

    def _write_table(
        self, stream: TextIO, prefix: tuple[str, ...], values: Mapping[str, object]
    ) -> None:
        scalar_items = [
            (name, value)
            for name, value in sorted(values.items())
            if not isinstance(value, Mapping)
        ]
        table_items = [
            (name, value)
            for name, value in sorted(values.items())
            if isinstance(value, Mapping)
        ]
        if prefix:
            stream.write(f"[{'.'.join(self._format_key(part) for part in prefix)}]\n")
        for name, value in scalar_items:
            stream.write(f"{self._format_key(name)} = {self._toml_literal(value)}\n")
        if prefix and (scalar_items or table_items):
            stream.write("\n")
        for index, (name, value) in enumerate(table_items):
            self._write_table(stream, (*prefix, name), value)
            if index + 1 < len(table_items):
                stream.write("\n")

    @staticmethod
    def _format_key(name: str) -> str:
        return name if _BARE_KEY.fullmatch(name) else json.dumps(name, ensure_ascii=False)

    @classmethod
    def _toml_literal(cls, value: object) -> str:
        if isinstance(value, Mapping):
            members = ", ".join(
                f"{cls._format_key(str(name))} = {cls._toml_literal(member)}"
                for name, member in value.items()
            )
            return f"{{ {members} }}"
        if isinstance(value, list):
            return "[" + ", ".join(cls._toml_literal(item) for item in value) + "]"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        return json.dumps(str(value), ensure_ascii=False)
