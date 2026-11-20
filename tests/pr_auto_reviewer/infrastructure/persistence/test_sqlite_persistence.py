"""Behavioral tests for encrypted SQLite persistence."""

import sqlite3
from pathlib import Path

import pytest

from pr_auto_reviewer.domain import CommitSha, PullRequest, PullRequestId
from pr_auto_reviewer.infrastructure.persistence.sqlite_persistence import (
    EncryptedSqliteSecretStore,
    SqlitePullRequestRepository,
)


class TestSqlitePersistence:
    """Verify review state and platform secrets are persisted safely."""

    @staticmethod
    def _pull_request() -> PullRequest:
        return PullRequest(
            id=PullRequestId(repository="owner/repo", number=42),
            title="Fix login bug",
            head_sha=CommitSha(value="abc123"),
        )

    def test_pull_request_round_trip_and_reset(self, tmp_path: Path) -> None:
        repository = SqlitePullRequestRepository(tmp_path / "state.sqlite3", "test-key")
        pull_request = self._pull_request()

        repository.save(pull_request)

        assert repository.find(pull_request.id) == pull_request
        repository.reset()
        assert repository.find(pull_request.id) is None

    def test_review_state_is_encrypted_at_rest(self, tmp_path: Path) -> None:
        database = tmp_path / "state.sqlite3"
        repository = SqlitePullRequestRepository(database, "test-key")
        pull_request = self._pull_request()

        repository.save(pull_request)

        with sqlite3.connect(database) as connection:
            raw = connection.execute(
                "SELECT payload FROM pull_requests"
            ).fetchone()[0]
        assert b"Fix login bug" not in raw
        assert b"abc123" not in raw

    def test_secret_store_overwrites_without_reading_metadata(self, tmp_path: Path) -> None:
        database = tmp_path / "secrets.sqlite3"
        store = EncryptedSqliteSecretStore(database, "test-key")

        store.set("GITHUB_OWNER_TOKEN", "secret-token")
        store.set("GITHUB_OWNER_TOKEN", "replacement-token")

        assert store.get("GITHUB_OWNER_TOKEN") == "replacement-token"
        assert store.names() == ("GITHUB_OWNER_TOKEN",)
        with sqlite3.connect(database) as connection:
            raw = connection.execute(
                "SELECT ciphertext FROM secrets"
            ).fetchone()[0]
        assert b"replacement-token" not in raw
        assert b"secret-token" not in raw

    def test_wrong_encryption_key_fails_closed(self, tmp_path: Path) -> None:
        database = tmp_path / "secrets.sqlite3"
        EncryptedSqliteSecretStore(database, "test-key").set("TOKEN", "value")

        with pytest.raises(ValueError, match="decrypt"):
            EncryptedSqliteSecretStore(database, "wrong-key").get("TOKEN")

    def test_storage_key_migration_reencrypts_state_and_secrets(
        self, tmp_path: Path,
    ) -> None:
        from pr_auto_reviewer.infrastructure.persistence.sqlite_persistence import (
            LEGACY_STORAGE_ENCRYPTION_KEY,
            SqliteStorageKeyMigrator,
        )

        state_database = tmp_path / "state.sqlite3"
        secrets_database = tmp_path / "secrets.sqlite3"
        pull_request = self._pull_request()
        SqlitePullRequestRepository(
            state_database, LEGACY_STORAGE_ENCRYPTION_KEY,
        ).save(pull_request)
        EncryptedSqliteSecretStore(
            secrets_database, LEGACY_STORAGE_ENCRYPTION_KEY,
        ).set("TOKEN", "value")

        assert SqliteStorageKeyMigrator(
            state_database, "configured-key",
        ).migrate()
        assert SqliteStorageKeyMigrator(
            secrets_database, "configured-key",
        ).migrate()

        assert SqlitePullRequestRepository(
            state_database, "configured-key",
        ).find(pull_request.id) == pull_request
        assert EncryptedSqliteSecretStore(
            secrets_database, "configured-key",
        ).get("TOKEN") == "value"

    def test_storage_key_migration_rejects_unknown_legacy_key(
        self, tmp_path: Path,
    ) -> None:
        from pr_auto_reviewer.infrastructure.persistence.sqlite_persistence import (
            LEGACY_STORAGE_ENCRYPTION_KEY,
            SqliteStorageKeyMigrator,
        )

        database = tmp_path / "state.sqlite3"
        pull_request = self._pull_request()
        SqlitePullRequestRepository(
            database, LEGACY_STORAGE_ENCRYPTION_KEY,
        ).save(pull_request)

        with pytest.raises(ValueError, match="decrypt"):
            SqliteStorageKeyMigrator(
                database, "configured-key", "wrong-legacy-key",
            ).migrate()

        assert SqlitePullRequestRepository(
            database, LEGACY_STORAGE_ENCRYPTION_KEY,
        ).find(pull_request.id) == pull_request
