"""CLI for non-secret TOML settings and encrypted platform credentials."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Sequence, cast

from dotenv import dotenv_values

from pr_auto_reviewer.infrastructure.config.app_paths import AppPaths
from pr_auto_reviewer.infrastructure.config.repository_entries_parser import (
    RepositoryEntriesParser,
)
from pr_auto_reviewer.infrastructure.config.settings_key_mapping import setting_key
from pr_auto_reviewer.infrastructure.config.toml_settings_store import (
    TomlSettingsStore,
)
from pr_auto_reviewer.infrastructure.persistence.sqlite_persistence import (
    EncryptedSqliteSecretStore,
)


@dataclass(frozen=True)
class SettingsSnapshot:
    """Non-secret settings and secret names without secret values."""

    values: tuple[tuple[str, str], ...]
    secret_names: tuple[str, ...]
    secret_error: str | None = None


class SettingsCli:
    """Read and write application settings without exposing credentials."""

    def run(self, argv: Sequence[str]) -> int:
        """Execute one settings command and return a process exit code."""
        parser = self._parser()
        args = parser.parse_args(list(argv))
        try:
            return self._dispatch(args)
        except ValueError as error:
            print(f"Error: {error}", file=os.sys.stderr)
            return 2

    def _parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="config")
        commands = parser.add_subparsers(dest="action", required=True)
        set_command = commands.add_parser("set")
        set_command.add_argument("name")
        set_command.add_argument("value")
        get_command = commands.add_parser("get")
        get_command.add_argument("name")
        delete_command = commands.add_parser("unset")
        delete_command.add_argument("name")
        commands.add_parser("set-encryption-key")
        add_repo = commands.add_parser("repo-add")
        add_repo.add_argument("repository")
        remove_repo = commands.add_parser("repo-remove")
        remove_repo.add_argument("repository")
        commands.add_parser("list")
        return parser

    def _dispatch(self, args: argparse.Namespace) -> int:
        if args.action == "set":
            return self._set(args.name, args.value)
        if args.action == "set-encryption-key":
            return self._set_encryption_key()
        if args.action == "get":
            return self._get(args.name)
        if args.action == "unset":
            return self._unset(args.name)
        if args.action == "repo-add":
            self.add_repository(
                args.repository,
                getpass.getpass("Manager token: "),
                getpass.getpass("Reviewer token: "),
            )
            print(f"Added repository {args.repository}")
            return 0
        if args.action == "repo-remove":
            self.remove_repository(args.repository)
            print(f"Removed repository {args.repository}")
            return 0
        return self._list()

    def navigation_mode(self) -> str:
        """Return the configured dashboard navigation mode."""
        value = self._settings().get("tui.navigation_mode", "arrows")
        return str(value).strip().lower() or "arrows"

    def snapshot(self) -> SettingsSnapshot:
        """Return editable settings while keeping secrets write-only."""
        values = tuple(
            (name, self._format_setting(name, value))
            for name, value in sorted(self._settings().all().items())
            if not TomlSettingsStore.is_secret_name(name)
        )
        try:
            secret_names = self._secrets().names()
        except ValueError as error:
            return SettingsSnapshot(
                values=values,
                secret_names=(),
                secret_error=str(error),
            )
        return SettingsSnapshot(values=values, secret_names=secret_names)

    def write(self, name: str, raw_value: str) -> None:
        """Write one setting without returning or logging its value."""
        if name == "PR_AUTO_REVIEWER_ENCRYPTION_KEY":
            self._write_encryption_key(raw_value)
            return
        key = setting_key(name)
        if key is not None and key.canonical_name == "repositories.allow_list":
            self._settings().set(
                name,
                cast(list[object], RepositoryEntriesParser().canonical_list(raw_value)),
            )
            return
        if TomlSettingsStore.is_secret_name(name):
            self._secrets().set(name, raw_value)
            return
        self._settings().set(name, self._parse_value(raw_value))
    def unset(self, name: str) -> None:
        """Remove one setting without exposing a secret value."""
        if TomlSettingsStore.is_secret_name(name):
            self._secrets().delete(name)
            return
        self._settings().delete(name)

    def add_repository(
        self, repository: str, manager_token: str, reviewer_token: str,
    ) -> None:
        """Allow a repository and store its platform role tokens."""
        platform, separator, scoped_name = repository.partition(":")
        if not separator or platform.upper() not in {"GITHUB", "FORGEJO"}:
            raise ValueError("repository must be platform:owner/name")
        owner, owner_separator, _name = scoped_name.partition("/")
        if not owner_separator or not owner:
            raise ValueError("repository must be platform:owner/name")
        if not manager_token or not reviewer_token:
            raise ValueError("manager and reviewer tokens are required")
        settings = self._settings()
        repositories = self._repositories()
        if repository not in repositories:
            repositories.append(repository)
            settings.set("repositories.allow_list", cast(list[object], repositories))
        prefix = platform.upper()
        self._secrets().set(f"{prefix}_TOKEN_{owner}_MANAGER", manager_token)
        self._secrets().set(f"{prefix}_TOKEN_{owner}_REVIEWER", reviewer_token)

    def remove_repository(self, repository: str) -> None:
        """Remove a repository from the allow list without deleting shared tokens."""
        repositories = [item for item in self._repositories() if item != repository]
        self._settings().set("repositories.allow_list", cast(list[object], repositories))

    def _repositories(self) -> list[str]:
        raw = self._settings().get("repositories.allow_list", [])
        return list(RepositoryEntriesParser().parse(raw))

    def _set_encryption_key(self) -> int:
        key = getpass.getpass("Encryption key: ").strip()
        if not key:
            raise ValueError("Encryption key must not be empty")
        self._write_encryption_key(key)
        print("Updated encryption key")
        return 0

    def _write_encryption_key(self, key: str) -> None:
        config_path = AppPaths.config_dir() / "config"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        lines = existing.splitlines(keepends=True)
        replacement = f"PR_AUTO_REVIEWER_ENCRYPTION_KEY={key}\n"
        updated: list[str] = []
        replaced = False
        for line in lines:
            if line.startswith("PR_AUTO_REVIEWER_ENCRYPTION_KEY="):
                if not replaced:
                    updated.append(replacement)
                    replaced = True
                continue
            updated.append(line)
        if not replaced:
            if updated and not updated[-1].endswith("\n"):
                updated.append("\n")
            updated.append(replacement)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f"{config_path.name}.",
            dir=config_path.parent,
            text=True,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write("".join(updated))
            os.chmod(temporary, 0o600)
            os.replace(temporary, config_path)
        except BaseException:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise

    def _set(self, name: str, raw_value: str) -> int:
        self.write(name, raw_value)
        label = "secret" if TomlSettingsStore.is_secret_name(name) else "setting"
        print(f"Updated {label} {name}")
        return 0

    def _get(self, name: str) -> int:
        if TomlSettingsStore.is_secret_name(name):
            print(f"Error: cannot read secret {name}", file=os.sys.stderr)
            return 2
        value = self._settings().get(name)
        if value is None:
            print(f"Error: setting {name} is not set", file=os.sys.stderr)
            return 1
        print(self._format_setting(name, value))
        return 0

    def _unset(self, name: str) -> int:
        self.unset(name)
        print(f"Removed {name}")
        return 0

    def _list(self) -> int:
        for name, value in sorted(self._settings().all().items()):
            if not TomlSettingsStore.is_secret_name(name):
                print(f"{name} = {self._format_setting(name, value)}")
        for name in self._secrets().names():
            print(f"{name} = <secret>")
        return 0

    @staticmethod
    def _parse_value(raw_value: str) -> str | int | float | bool | list[object] | dict[str, object]:
        lowered = raw_value.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            return raw_value

    @staticmethod
    def _format_value(value: object) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _format_setting(name: str, value: object) -> str:
        key = setting_key(name)
        if key is not None and key.canonical_name == "repositories.allow_list":
            return json.dumps(
                RepositoryEntriesParser().canonical_list(value),
                ensure_ascii=False,
            )
        return SettingsCli._format_value(value)

    @staticmethod
    def _settings() -> TomlSettingsStore:
        return TomlSettingsStore(AppPaths.config_dir() / "settings.toml")

    @staticmethod
    def _encryption_key() -> str:
        key = os.environ.get("PR_AUTO_REVIEWER_ENCRYPTION_KEY", "").strip()
        if not key:
            configured = dotenv_values(AppPaths.config_dir() / "config")
            key = str(
                configured.get("PR_AUTO_REVIEWER_ENCRYPTION_KEY", "") or "",
            ).strip()
        if not key:
            raise ValueError("PR_AUTO_REVIEWER_ENCRYPTION_KEY is required")
        return key

    @classmethod
    def _secrets(cls) -> EncryptedSqliteSecretStore:
        return EncryptedSqliteSecretStore(
            AppPaths.state_dir() / "secrets.sqlite3",
            cls._encryption_key(),
        )
