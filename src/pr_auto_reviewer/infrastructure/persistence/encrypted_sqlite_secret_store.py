"""Encrypted SQLite secret storage."""

from __future__ import annotations

from pathlib import Path

from .sqlite_cipher import SqliteCipher
from .sqlite_database import SqliteDatabase


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


    def validate_key(self) -> bool:
        """Validate the key against all stored ciphertexts.

        Return ``False`` when the store has no encrypted records, because an
        empty store cannot prove that the key matches persisted data.
        """
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT ciphertext FROM secrets"
            ).fetchall()
        if not rows:
            return False
        for (ciphertext,) in rows:
            self._cipher.decrypt(ciphertext)
        return True

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
