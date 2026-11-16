"""Encrypted SQLite adapters for review state and platform credentials."""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from ...domain.entities.pull_request import PullRequest
from ...domain.value_objects.pull_request_id import PullRequestId
from .json_file_pr_repository import JsonFilePullRequestRepository


class SqliteCipher:
    """Encrypt and decrypt application data with a caller-provided key."""

    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError("Encryption key must not be empty")
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, value: str) -> bytes:
        """Return encrypted UTF-8 data."""
        return self._fernet.encrypt(value.encode("utf-8"))

    def decrypt(self, value: bytes) -> str:
        """Return decrypted UTF-8 data or fail closed."""
        try:
            return self._fernet.decrypt(value).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise ValueError("Unable to decrypt persisted data") from exc


class SqliteDatabase:
    """Initialize and open the SQLite database used by persistence adapters."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        """Open a connection and ensure the schema exists."""
        connection = sqlite3.connect(self._database_path)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pull_requests (
                repository TEXT NOT NULL,
                number INTEGER NOT NULL,
                payload BLOB NOT NULL,
                PRIMARY KEY (repository, number)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS secrets (
                name TEXT PRIMARY KEY,
                ciphertext BLOB NOT NULL
            )
            """
        )
        connection.commit()
        return connection


class SqlitePullRequestRepository(JsonFilePullRequestRepository):
    """Persist pull-request aggregates as encrypted SQLite payloads."""

    def __init__(self, database_path: str | Path, encryption_key: str) -> None:
        super().__init__(Path(database_path))
        self._database = SqliteDatabase(database_path)
        self._cipher = SqliteCipher(encryption_key)

    def find(self, pr_id: PullRequestId) -> PullRequest | None:
        """Load one pull request by repository and number."""
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM pull_requests WHERE repository = ? AND number = ?",
                (pr_id.repository, pr_id.number),
            ).fetchone()
        if row is None:
            return None
        raw = json.loads(self._cipher.decrypt(row[0]))
        return self._deserialize(pr_id, raw)

    def save(self, pr: PullRequest) -> None:
        """Encrypt and upsert one pull-request aggregate."""
        payload = json.dumps(self._serialize(pr), ensure_ascii=False)
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO pull_requests(repository, number, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(repository, number) DO UPDATE SET payload = excluded.payload
                """,
                (pr.id.repository, pr.id.number, self._cipher.encrypt(payload)),
            )
            connection.commit()

    def reset(self) -> None:
        """Delete all persisted pull-request aggregates."""
        with self._database.connect() as connection:
            connection.execute("DELETE FROM pull_requests")
            connection.commit()


class EncryptedSqliteSecretStore:
    """Store named secrets encrypted in SQLite without exposing values by listing."""

    def __init__(self, database_path: str | Path, encryption_key: str) -> None:
        self._database = SqliteDatabase(database_path)
        self._cipher = SqliteCipher(encryption_key)

    def set(self, name: str, value: str) -> None:
        """Create or replace a named secret."""
        if not name:
            raise ValueError("Secret name must not be empty")
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO secrets(name, ciphertext) VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET ciphertext = excluded.ciphertext
                """,
                (name, self._cipher.encrypt(value)),
            )
            connection.commit()

    def get(self, name: str) -> str | None:
        """Return one secret value, or ``None`` when it does not exist."""
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT ciphertext FROM secrets WHERE name = ?", (name,)
            ).fetchone()
        return None if row is None else self._cipher.decrypt(row[0])

    def names(self) -> tuple[str, ...]:
        """Return secret names without returning secret values."""
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT name FROM secrets ORDER BY name"
            ).fetchall()
        return tuple(row[0] for row in rows)

    def delete(self, name: str) -> None:
        """Delete a named secret when present."""
        with self._database.connect() as connection:
            connection.execute("DELETE FROM secrets WHERE name = ?", (name,))
            connection.commit()
