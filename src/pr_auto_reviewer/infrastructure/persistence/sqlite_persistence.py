"""Compatibility exports for encrypted SQLite persistence adapters."""

from .encrypted_sqlite_secret_store import EncryptedSqliteSecretStore
from .encryption_key_error import EncryptionKeyError
from .sqlite_cipher import SqliteCipher
from .sqlite_database import SqliteDatabase
from .sqlite_pull_request_repository import SqlitePullRequestRepository
from .sqlite_storage_key_migrator import (
    LEGACY_STORAGE_ENCRYPTION_KEY,
    SqliteStorageKeyMigrator,
)

__all__ = [
    "LEGACY_STORAGE_ENCRYPTION_KEY",
    "EncryptedSqliteSecretStore",
    "EncryptionKeyError",
    "SqliteCipher",
    "SqliteDatabase",
    "SqlitePullRequestRepository",
    "SqliteStorageKeyMigrator",
]
