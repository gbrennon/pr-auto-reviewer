"""Tests for dotenv token migration into encrypted SQLite."""

from __future__ import annotations

from pathlib import Path
from runpy import run_path
from typing import Any

import pytest

from pr_auto_reviewer.infrastructure.persistence.sqlite_persistence import (
    EncryptedSqliteSecretStore,
)

TokenMigration: Any = run_path(
    str(Path(__file__).parents[2] / "scripts" / "migrate_tokens.py")
)["TokenMigration"]


class TestTokenMigration:
    """Verify token migration boundaries and file behavior."""

    def test_dry_run_lists_tokens_without_key_or_changes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        source = tmp_path / "config"
        source.write_text(
            "PR_AUTO_REVIEWER_ENCRYPTION_KEY=keep-key\n"
            "FORGEJO_MANAGER_TOKEN=manager-token\n"
            "PLATFORM_MODE=forgejo\n",
            encoding="utf-8",
        )
        monkeypatch.delenv("PR_AUTO_REVIEWER_ENCRYPTION_KEY", raising=False)

        assert TokenMigration.main(
            [
                "--dry-run",
                "--source",
                str(source),
                "--database",
                str(tmp_path / "secrets.sqlite3"),
            ]
        ) == 0

        output = capsys.readouterr().out
        assert "Would migrate 1 token entries" in output
        assert "FORGEJO_MANAGER_TOKEN" in output
        assert "manager-token" not in output
        assert source.read_text(encoding="utf-8").count("FORGEJO_MANAGER_TOKEN") == 1
        assert not (tmp_path / "secrets.sqlite3").exists()

    def test_migration_stores_tokens_and_preserves_non_tokens(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        source = tmp_path / "config"
        source.write_text(
            "# keep this comment\n"
            "PR_AUTO_REVIEWER_ENCRYPTION_KEY=keep-key\n"
            "FORGEJO_MANAGER_TOKEN=manager-token\n"
            "FORGEJO_TOKEN_senkai_REVIEWER=org-reviewer-token\n"
            "FORGEJO_TOKEN_invalid=not-a-token-entry\n"
            "PLATFORM_MODE=forgejo\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("PR_AUTO_REVIEWER_ENCRYPTION_KEY", "keep-key")
        database = tmp_path / "secrets.sqlite3"

        assert TokenMigration.main(
            ["--source", str(source), "--database", str(database)]
        ) == 0

        output = capsys.readouterr().out
        store = EncryptedSqliteSecretStore(database, "keep-key")
        assert set(store.names()) == {
            "FORGEJO_MANAGER_TOKEN",
            "FORGEJO_TOKEN_senkai_REVIEWER",
        }
        retained = source.read_text(encoding="utf-8")
        assert "PR_AUTO_REVIEWER_ENCRYPTION_KEY=keep-key" in retained
        assert "PLATFORM_MODE=forgejo" in retained
        assert "FORGEJO_TOKEN_invalid=not-a-token-entry" in retained
        assert "FORGEJO_MANAGER_TOKEN=manager-token" not in retained
        assert "manager-token" not in output
        assert "org-reviewer-token" not in output

    def test_missing_source_returns_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("PR_AUTO_REVIEWER_ENCRYPTION_KEY", "keep-key")

        assert TokenMigration.main(
            [
                "--source",
                str(tmp_path / "missing"),
                "--database",
                str(tmp_path / "secrets.sqlite3"),
            ]
        ) == 2

        assert "Config file not found" in capsys.readouterr().err
