"""CLI for non-secret TOML settings and encrypted platform credentials."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from dotenv import dotenv_values

from pr_auto_reviewer.infrastructure.config.app_paths import AppPaths
from pr_auto_reviewer.infrastructure.config.toml_settings_store import (
    TomlSettingsStore,
)
from pr_auto_reviewer.infrastructure.persistence.sqlite_persistence import (
    EncryptedSqliteSecretStore,
)


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
        commands.add_parser("list")
        return parser

    def _dispatch(self, args: argparse.Namespace) -> int:
        if args.action == "set":
            return self._set(args.name, args.value)
        if args.action == "get":
            return self._get(args.name)
        if args.action == "unset":
            return self._unset(args.name)
        return self._list()

    def _set(self, name: str, raw_value: str) -> int:
        if TomlSettingsStore.is_secret_name(name):
            self._secrets().set(name, raw_value)
            print(f"Updated secret {name}")
            return 0
        self._settings().set(name, self._parse_value(raw_value))
        print(f"Updated setting {name}")
        return 0

    def _get(self, name: str) -> int:
        if TomlSettingsStore.is_secret_name(name):
            print(f"Error: cannot read secret {name}", file=os.sys.stderr)
            return 2
        value = self._settings().get(name)
        if value is None:
            print(f"Error: setting {name} is not set", file=os.sys.stderr)
            return 1
        print(self._format_value(value))
        return 0

    def _unset(self, name: str) -> int:
        if TomlSettingsStore.is_secret_name(name):
            self._secrets().delete(name)
        else:
            self._settings().delete(name)
        print(f"Removed {name}")
        return 0

    def _list(self) -> int:
        for name, value in sorted(self._settings().all().items()):
            print(f"{name} = {self._format_value(value)}")
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
