"""Migrate the legacy dotenv configuration into the new stores."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Sequence, cast

from pr_auto_reviewer.infrastructure.config.app_paths import AppPaths
from pr_auto_reviewer.infrastructure.config.repository_entries_parser import (
    RepositoryEntriesParser,
)
from pr_auto_reviewer.infrastructure.config.settings_key_mapping import (
    canonical_name,
    setting_key,
)
from pr_auto_reviewer.infrastructure.config.toml_settings_store import (
    TomlSettingsStore,
    TomlValue,
)
from pr_auto_reviewer.infrastructure.persistence.encrypted_sqlite_secret_store import (
    EncryptedSqliteSecretStore,
)


_STALE_SETTING_NAMES = (
    "LLM_BACKEND",
    "PUBLISH_INCONCLUSIVE_REVIEW",
    "USE_LOCAL_CLONE",
    "Select.NULL",
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
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._source = Path(source)
        self._config_dir = Path(config_dir)
        self._state_dir = Path(state_dir)
        self._encryption_key = encryption_key
        self._dry_run = dry_run
        self._ignored_names: set[str] = set()
        self._environment = dict(os.environ if environment is None else environment)

    def run(self) -> dict[str, tuple[str, ...]]:
        """Migrate values and return the migrated setting and secret names."""
        source_values = self._read_source()
        values = {
            self._canonical_secret_name(name): value
            for name, value in source_values.items()
            if not (
                name.endswith("_OWNER_TOKEN")
                and self._canonical_secret_name(name) in source_values
            )
        }
        settings = tuple(name for name in values if not TomlSettingsStore.is_secret_name(name))
        secrets = tuple(name for name in values if TomlSettingsStore.is_secret_name(name))
        if not self._dry_run:
            if secrets and not self._encryption_key:
                raise ValueError("An encryption key is required when migrating secrets")
            self._wipe_secret_store()
            if self._encryption_key:
                self._write_runtime_environment()
            self._write_settings(values, settings)
            self._write_secrets(values, secrets)
            self._remove_ignored_settings()
        return {"settings": settings, "secrets": secrets}

    def _write_runtime_environment(self) -> None:
        environment_path = self._config_dir / "environment"
        environment_path.parent.mkdir(parents=True, exist_ok=True)
        environment_path.write_text(
            "PR_AUTO_REVIEWER_ENCRYPTION_KEY="
            + shlex.quote(self._encryption_key)
            + "\n"
        )
        environment_path.chmod(0o600)
        service_path = Path.home() / ".config/systemd/user/pr-auto-reviewer.service"
        if service_path.is_file():
            content = service_path.read_text()
            directive = "EnvironmentFile=%h/.config/pr-auto-reviewer/environment"
            if directive not in content:
                marker = "[Service]\n"
                if marker in content:
                    service_path.write_text(content.replace(marker, marker + directive + "\n", 1))

    def _wipe_secret_store(self) -> None:
        database_paths = (
            self._state_dir / "secrets.sqlite3",
            self._state_dir / "state.sqlite3",
        )
        for database_path in database_paths:
            for path in (
                database_path,
                Path(f"{database_path}-wal"),
                Path(f"{database_path}-shm"),
            ):
                if path.exists():
                    path.unlink()

    def _remove_ignored_settings(self) -> None:
        store = TomlSettingsStore(self._config_dir / "settings.toml")
        for name in (*self._ignored_names, *_STALE_SETTING_NAMES):
            store.delete(name)


    def _read_source(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if self._source.is_file():
            for line in self._source.read_text().splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                name, separator, value = stripped.partition("=")
                clean_name = name.strip()
                if not separator or not clean_name:
                    raise ValueError(f"Invalid legacy config line: {line}")
                if self._is_migratable_name(clean_name):
                    values[clean_name] = value.strip().strip('"').strip("'")
                elif clean_name != "PR_AUTO_REVIEWER_ENCRYPTION_KEY":
                    self._ignored_names.add(clean_name)
        for name, value in self._environment.items():
            if self._is_migratable_name(name):
                values.setdefault(name, value)
        if not values and not self._source.is_file():
            raise ValueError(f"Source config does not exist: {self._source}")
        return values

    def _is_migratable_name(self, name: str) -> bool:
        return (
            name != "PR_AUTO_REVIEWER_ENCRYPTION_KEY"
            and (
                TomlSettingsStore.is_secret_name(name)
                or setting_key(name) is not None
            )
        )

    def _write_settings(self, values: dict[str, str], names: tuple[str, ...]) -> None:
        if not names:
            return
        store = TomlSettingsStore(self._config_dir / "settings.toml")
        for name in names:
            value = (
                RepositoryEntriesParser().canonical_list(values[name])
                if name.upper() == "REPOS_ALLOW_LIST"
                else self._parse_value(values[name])
            )
            store.set(canonical_name(name), cast(TomlValue, value))
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
            store.set(self._canonical_secret_name(name), values[name])
        settings_store = TomlSettingsStore(self._config_dir / "settings.toml")
        for name in names:
            canonical_name_value = self._canonical_secret_name(name)
            settings_store.delete(name)
            settings_store.delete(canonical_name_value)
            settings_store.delete(self._legacy_secret_name(canonical_name_value))

    def _canonical_secret_name(self, name: str) -> str:
        if name.endswith("_OWNER_TOKEN"):
            return name.removesuffix("_OWNER_TOKEN") + "_MANAGER_TOKEN"
        if name.endswith("_OWNER"):
            return name.removesuffix("_OWNER") + "_MANAGER"
        return name

    def _legacy_secret_name(self, name: str) -> str:
        if name.endswith("_MANAGER_TOKEN"):
            return name.removesuffix("_MANAGER_TOKEN") + "_OWNER_TOKEN"
        if name.endswith("_MANAGER"):
            return name.removesuffix("_MANAGER") + "_OWNER"
        return name
    def _parse_value(self, raw_value: str) -> str | int | float | bool | list[object] | dict[str, object]:
        lowered = raw_value.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            return raw_value

    def _source_encryption_key(self) -> str:
        if not self._source.is_file():
            return ""
        for line in self._source.read_text().splitlines():
            name, separator, value = line.strip().partition("=")
            if separator and name.strip() == "PR_AUTO_REVIEWER_ENCRYPTION_KEY":
                return value.strip().strip('"').strip("'")
        return ""

    @classmethod
    def from_cli(cls, argv: Sequence[str] | None = None) -> ConfigMigration:
        """Create a migration from command-line arguments."""
        parser = argparse.ArgumentParser(
            description="Copy legacy dotenv settings into the new stores"
        )
        parser.add_argument("--source", type=Path, default=Path("config"))
        parser.add_argument("--config-dir", type=Path, default=AppPaths.config_dir())
        parser.add_argument("--state-dir", type=Path, default=AppPaths.state_dir())
        parser.add_argument("--encryption-key")
        parser.add_argument("--dry-run", action="store_true")
        args = parser.parse_args(argv)
        probe = cls(args.source, args.config_dir, args.state_dir, "")
        encryption_key = (
            args.encryption_key
            or os.environ.get("PR_AUTO_REVIEWER_ENCRYPTION_KEY", "")
            or probe._source_encryption_key()
        )
        return cls(
            source=args.source,
            config_dir=args.config_dir,
            state_dir=args.state_dir,
            encryption_key=encryption_key,
            dry_run=args.dry_run,
        )

    def main(self) -> int:
        """Run the migration and return its process exit code."""
        try:
            result = self.run()
        except ValueError as error:
            raise SystemExit(str(error)) from error
        action = "Would migrate" if self._dry_run else "Migrated"
        print(f"{action} {len(result['settings'])} settings and {len(result['secrets'])} secrets")
        return 0


if __name__ == "__main__":
    raise SystemExit(ConfigMigration.from_cli().main())
