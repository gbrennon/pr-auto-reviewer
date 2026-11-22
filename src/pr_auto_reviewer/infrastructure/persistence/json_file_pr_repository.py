"""JsonFilePullRequestRepository — persistence adapter for PullRequest aggregate.

Implements PullRequestRepositoryPort. Replaces the STATE_FILE bash script approach
with atomic writes and structured deserialization.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from ...application.ports.outbound.pull_request_repository_port import (
    PullRequestRepositoryPort,
)
from ...domain.entities.pull_request import PullRequest
from ...domain.exceptions import RepositoryCorruptedError
from ...domain.value_objects.code_review import CodeReview
from ...domain.value_objects.comment_id import CommentId
from ...domain.value_objects.commit_sha import CommitSha
from ...domain.value_objects.pull_request_id import PullRequestId
from ...domain.value_objects.review_item_lifecycle import ReviewItemLifecycle

logger = logging.getLogger(__name__)

_STATE_KEY_SEPARATOR = "/"


from .code_review_codec import CodeReviewCodec
from .review_item_codec import ReviewItemCodec
from .review_item_lifecycle_codec import ReviewItemLifecycleCodec
from .state_key import StateKey


class JsonFilePullRequestRepository(PullRequestRepositoryPort):
    """Serialize and deserialize the PullRequest aggregate to a local JSON file.

    Atomic writes: writes to a .tmp sibling file, then os.replace() to avoid
    partial writes on crash.
    """

    def __init__(self, file_path: str | Path) -> None:
        self._file_path = Path(file_path)

    def find(self, pr_id: PullRequestId) -> PullRequest | None:
        data = self._load()
        reviewed = data.get("reviewed", {})

        key = StateKey.of(pr_id)
        raw = reviewed.get(key)
        if raw is None:
            return None

        return self._deserialize(pr_id, raw)

    def save(self, pr: PullRequest) -> None:
        data = self._load()
        reviewed = data.setdefault("reviewed", {})

        key = StateKey.of(pr.id)
        reviewed[key] = self._serialize(pr)

        self._save(data)

    def reset(self) -> None:
        """Clear all persisted state by deleting and recreating the file."""
        logger.info("Resetting state file %s", self._file_path)
        if self._file_path.exists():
            self._file_path.unlink()
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_path.write_text('{"reviewed":{}}')

    def _load(self) -> dict:
        if not self._file_path.exists():
            return {"reviewed": {}}
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise RepositoryCorruptedError(
                f"State file {self._file_path} is corrupted or unreadable"
            ) from exc

    def _deserialize(self, pr_id: PullRequestId, raw: dict) -> PullRequest:
        reviews_raw = raw.get("reviews", [])
        reviews: tuple[CodeReview, ...] = tuple(
            CodeReviewCodec.deserialize(r)
            for r in reviews_raw
        )
        unresolved_ids: frozenset[str] = frozenset(
            raw.get("unresolved_blocking_ids", [])
        )
        created_issue_item_ids: frozenset[str] = frozenset(
            raw.get("created_issue_item_ids", [])
        )
        dismissed_item_ids: frozenset[str] = frozenset(
            raw.get("dismissed_item_ids", [])
        )
        lifecycles: tuple[ReviewItemLifecycle, ...] = tuple(
            ReviewItemLifecycleCodec.deserialize(raw_lifecycle)
            for raw_lifecycle in raw.get("lifecycles", [])
        )
        processed_ids: frozenset[CommentId] = frozenset(
            CommentId(str(cid))
            for cid in raw.get("processed_comment_ids", [])
        )
        return PullRequest(
            id=pr_id,
            title=raw.get("title", ""),
            head_sha=CommitSha(raw.get("head_sha", "")),
            unresolved_blocking_ids=unresolved_ids,
            created_issue_item_ids=created_issue_item_ids,
            dismissed_item_ids=dismissed_item_ids,
            last_reviewed_at=raw.get("last_reviewed_at"),
            is_draft=raw.get("is_draft", False),
            reviews=reviews,
            processed_comment_ids=processed_ids,
            last_review_request_event_id=raw.get(
                "last_review_request_event_id"
            ),
            last_platform_review_id=raw.get("last_platform_review_id"),
            last_platform_review_dismissed=raw.get(
                "last_platform_review_dismissed", False
            ),
            last_inconclusive_sha=(
                CommitSha(raw["last_inconclusive_sha"])
                if raw.get("last_inconclusive_sha")
                else None
            ),
            last_command_checked_at=raw.get("last_command_checked_at"),
            lifecycles=lifecycles,
        ).with_derived_lifecycles()

    def _save(self, data: dict) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=self._file_path.name,
            dir=self._file_path.parent,
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self._file_path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _serialize(self, pr: PullRequest) -> dict:

        return {
            "title": pr.title,
            "head_sha": str(pr.head_sha),
            "is_draft": pr.is_draft,
            "reviews": [CodeReviewCodec.serialize(r) for r in pr.reviews],
            "lifecycles": [
                ReviewItemLifecycleCodec.serialize(lifecycle)
                for lifecycle in pr.lifecycles
            ],
            "unresolved_blocking_ids": sorted(pr.unresolved_blocking_ids),
            "created_issue_item_ids": sorted(pr.created_issue_item_ids),
            "dismissed_item_ids": sorted(pr.dismissed_item_ids),
            "last_reviewed_at": pr.last_reviewed_at,
            "processed_comment_ids": sorted(
                str(c) for c in pr.processed_comment_ids
            ),
            "last_review_request_event_id": pr.last_review_request_event_id,
            "last_platform_review_id": pr.last_platform_review_id,
            "last_platform_review_dismissed": pr.last_platform_review_dismissed,
            "last_inconclusive_sha": (
                str(pr.last_inconclusive_sha)
                if pr.last_inconclusive_sha is not None
                else None
            ),
            "last_command_checked_at": pr.last_command_checked_at,
        }
