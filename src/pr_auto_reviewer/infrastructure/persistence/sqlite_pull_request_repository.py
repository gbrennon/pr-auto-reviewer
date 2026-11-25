"""Encrypted SQLite pull-request repository."""

from __future__ import annotations

import json
from pathlib import Path

from ...domain.entities.pull_request import PullRequest
from ...domain.value_objects.pull_request_id import PullRequestId
from .json_file_pr_repository import JsonFilePullRequestRepository
from .sqlite_cipher import SqliteCipher
from .sqlite_database import SqliteDatabase


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
