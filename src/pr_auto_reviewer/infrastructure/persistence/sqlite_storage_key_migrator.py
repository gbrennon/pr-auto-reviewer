"""Compatibility migration for encrypted SQLite storage keys."""

from __future__ import annotations

from pathlib import Path

from .sqlite_cipher import SqliteCipher
from .sqlite_database import SqliteDatabase

LEGACY_STORAGE_ENCRYPTION_KEY = "pr-auto-reviewer-local-key"


class SqliteStorageKeyMigrator:
    """Re-encrypt legacy SQLite payloads with the configured storage key."""

    _ENCRYPTED_COLUMNS = (
        ("pull_requests", "payload"),
        ("secrets", "ciphertext"),
    )

    def __init__(
        self,
        database_path: str | Path,
        encryption_key: str,
        legacy_key: str = LEGACY_STORAGE_ENCRYPTION_KEY,
    ) -> None:
        self._database_path = Path(database_path)
        self._encryption_key = encryption_key
        self._legacy_key = legacy_key
        self._current_cipher = SqliteCipher(encryption_key)
        self._legacy_cipher = SqliteCipher(legacy_key)

    def migrate(self) -> bool:
        """Re-encrypt legacy rows and return whether any row changed."""
        if not self._database_path.is_file():
            return False
        if self._encryption_key == self._legacy_key:
            return False
        changed = False
        database = SqliteDatabase(self._database_path)
        with database.connect() as connection:
            for table, column in self._ENCRYPTED_COLUMNS:
                rows = connection.execute(
                    f"SELECT rowid, {column} FROM {table}"
                ).fetchall()
                for row_id, ciphertext in rows:
                    replacement = self._reencrypt(ciphertext)
                    if replacement is None:
                        continue
                    connection.execute(
                        f"UPDATE {table} SET {column} = ? WHERE rowid = ?",
                        (replacement, row_id),
                    )
                    changed = True
        return changed

    def _reencrypt(self, ciphertext: bytes) -> bytes | None:
        try:
            self._current_cipher.decrypt(ciphertext)
        except ValueError:
            plaintext = self._legacy_cipher.decrypt(ciphertext)
            return self._current_cipher.encrypt(plaintext)
        return None
