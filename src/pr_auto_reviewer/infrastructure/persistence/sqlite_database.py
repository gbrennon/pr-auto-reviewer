"""SQLite schema and connection management."""

from __future__ import annotations

import sqlite3
from pathlib import Path


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
