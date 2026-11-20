"""Migrate token credentials from the user config file into encrypted SQLite."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from dotenv import dotenv_values

from pr_auto_reviewer.infrastructure.config.app_paths import AppPaths
from pr_auto_reviewer.infrastructure.config.role_suffix_parser import RoleSuffixParser
from pr_auto_reviewer.infrastructure.persistence.sqlite_persistence import (
    EncryptedSqliteSecretStore,
)


class TokenMigration:
    """Move supported token credentials without exposing their values."""

    _KEY_NAME = "PR_AUTO_REVIEWER_ENCRYPTION_KEY"
    _GLOBAL_SECRET_NAMES = frozenset(
        {
            "GITHUB_OWNER_TOKEN",
            "GITHUB_REVIEWER_TOKEN",
            "GITHUB_REVIEWER_USERNAME",
            "FORGEJO_OWNER_TOKEN",
            "FORGEJO_REVIEWER_TOKEN",
            "FORGEJO_REVIEWER_USERNAME",
        }
    )
    _TOKEN_PREFIXES = ("GITHUB_TOKEN_", "FORGEJO_TOKEN_")

    def __init__(
        self,
        source: Path,
        database: Path,
        key: str,
        dry_run: bool,
    ) -> None:
        self._source = source
        self._database = database
        self._key = key
        self._dry_run = dry_run

    def run(self) -> tuple[str, ...]:
        """Migrate token names and return the migrated names."""
        values = self._read_source()
        names = tuple(name for name in values if self._is_token_name(name))
        if not names:
            return ()
        if self._dry_run:
            return names
        store = EncryptedSqliteSecretStore(self._database, self._key)
        for name in names:
            store.set(name, values[name])
        self._remove_migrated_entries(names)
        return names

    def _read_source(self) -> dict[str, str]:
        if not self._source.is_file():
            raise FileNotFoundError(f"Config file not found: {self._source}")
        values = dotenv_values(self._source)
        return {name: value for name, value in values.items() if value is not None}

    def _is_token_name(self, name: str) -> bool:
        if name == self._KEY_NAME:
            return False
        if name in self._GLOBAL_SECRET_NAMES:
            return True
        for prefix in self._TOKEN_PREFIXES:
            if name.startswith(prefix):
                _, role = RoleSuffixParser.parse(name[len(prefix):])
                return bool(role)
        return False

    def _remove_migrated_entries(self, names: tuple[str, ...]) -> None:
        migrated = set(names)
        original = self._source.read_text(encoding="utf-8")
        retained = "".join(
            line
            for line in original.splitlines(keepends=True)
            if self._line_name(line) not in migrated
        )
        descriptor, temporary = tempfile.mkstemp(
            prefix=f"{self._source.name}.",
            dir=self._source.parent,
            text=True,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(retained)
            os.chmod(temporary, self._source.stat().st_mode & 0o777)
            os.replace(temporary, self._source)
        except BaseException:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise

    @staticmethod
    def _line_name(line: str) -> str | None:
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            return None
        if candidate.startswith("export "):
            candidate = candidate[7:].lstrip()
        if "=" not in candidate:
            return None
        return candidate.split("=", 1)[0].strip()

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> TokenMigration:
        source = Path(args.source).expanduser()
        database = Path(args.database).expanduser()
        key = ""
        if not args.dry_run:
            key = os.environ.get(cls._KEY_NAME, "").strip()
            if not key:
                key = getpass.getpass("Encryption key: ").strip()
            if not key:
                raise ValueError("Encryption key must not be empty")
        return cls(source, database, key, args.dry_run)

    @classmethod
    def main(cls, argv: Sequence[str] | None = None) -> int:
        """Run the token migration and return a process exit code."""
        parser = argparse.ArgumentParser(
            description="Move config-file tokens into encrypted SQLite storage",
        )
        parser.add_argument(
            "--source",
            default=str(AppPaths.config_dir() / "config"),
            help="dotenv config file containing token entries",
        )
        parser.add_argument(
            "--database",
            default=str(AppPaths.state_dir() / "secrets.sqlite3"),
            help="encrypted SQLite database path",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="list token names without changing files",
        )
        args = parser.parse_args(argv)
        try:
            names = cls.from_args(args).run()
        except (FileNotFoundError, ValueError) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 2
        if args.dry_run:
            print(f"Would migrate {len(names)} token entries")
        else:
            print(f"Migrated {len(names)} token entries")
        for name in names:
            print(name)
        return 0


if __name__ == "__main__":
    raise SystemExit(TokenMigration.main())
