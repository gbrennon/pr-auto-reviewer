"""Migrate the legacy dotenv configuration into the new stores."""

from __future__ import annotations

import argparse
import json
import os
import tomllib
from pathlib import Path
from typing import Sequence

from pr_auto_reviewer.infrastructure.config.app_paths import AppPaths
from pr_auto_reviewer.infrastructure.config.toml_settings_store import TomlSettingsStore
from pr_auto_reviewer.infrastructure.persistence.encrypted_sqlite_secret_store import (
    EncryptedSqliteSecretStore,
)


class ConfigMigration:
    """Copy legacy configuration values without modifying the source file."""

    def __init__(
        self,
        source: str | Path,
        config_dir: str | Path,
        state_dir: str | Path,
        encryption_key: str,
        dry_run: bool = False,
    ) -> None:
        self._source = Path(source)
        self._config_dir = Path(config_dir)
        self._state_dir = Path(state_dir)
        self._encryption_key = encryption_key
        self._dry_run = dry_run

    def run(self) -> dict[str, tuple[str, ...]]:
        """Migrate values and return the migrated setting and secret names."""
        values = self._read_source()
        settings = tuple(name for name in values if not TomlSettingsStore.is_secret_name(name))
        secrets = tuple(name for name in values if TomlSettingsStore.is_secret_name(name))
        if not self._dry_run:
            self._write_settings(values, settings)
            self._write_secrets(values, secrets)
        return {"settings": settings, "secrets": secrets}

    def _read_source(self) -> dict[str, str]:
        if not self._source.is_file():
            raise ValueError(f"Source config does not exist: {self._source}")
        values: dict[str, str] = {}
        for line in self._source.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            name, separator, value = stripped.partition("=")
            if not separator or not name.strip():
                raise ValueError(f"Invalid legacy config line: {line}")
            values[name.strip()] = value.strip().strip('"').strip("'")
        return values

    def _write_settings(self, values: dict[str, str], names: tuple[str, ...]) -> None:
        store = TomlSettingsStore(self._config_dir / "settings.toml")
        for name in names:
            store.set(name, self._parse_value(values[name]))
        with (self._config_dir / "settings.toml").open("rb") as stream:
            tomllib.load(stream)

    def _write_secrets(self, values: dict[str, str], names: tuple[str, ...]) -> None:
        if names and not self._encryption_key:
            raise ValueError("An encryption key is required when migrating secrets")
        if not names:
            return
        store = EncryptedSqliteSecretStore(
            self._state_dir / "secrets.sqlite3", self._encryption_key
        )
        for name in names:
            store.set(name, values[name])

    @staticmethod
    def _parse_value(raw_value: str) -> str | int | float | bool | list[object] | dict[str, object]:
        lowered = raw_value.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            return raw_value

    @classmethod
    def main(cls, argv: Sequence[str] | None = None) -> int:
        """Run the migration script and return its process exit code."""
        parser = cls._parser()
        args = parser.parse_args(argv)
        encryption_key = args.encryption_key or os.environ.get(
            "PR_AUTO_REVIEWER_ENCRYPTION_KEY", ""
        )
        try:
            result = cls(
                source=args.source,
                config_dir=args.config_dir,
                state_dir=args.state_dir,
                encryption_key=encryption_key,
                dry_run=args.dry_run,
            ).run()
        except ValueError as error:
            parser.error(str(error))
        action = "Would migrate" if args.dry_run else "Migrated"
        print(f"{action} {len(result['settings'])} settings and {len(result['secrets'])} secrets")
        return 0

    @staticmethod
    def _parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description="Copy legacy dotenv settings into the new stores"
        )
        parser.add_argument("--source", type=Path, default=Path("config"))
        parser.add_argument("--config-dir", type=Path, default=AppPaths.config_dir())
        parser.add_argument("--state-dir", type=Path, default=AppPaths.state_dir())
        parser.add_argument("--encryption-key")
        parser.add_argument("--dry-run", action="store_true")
        return parser


if __name__ == "__main__":
    raise SystemExit(ConfigMigration.main())
