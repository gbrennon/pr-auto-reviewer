"""JsonFilePullRequestRepository — persistence adapter for PullRequest aggregate.

Implements PullRequestRepository. Replaces the STATE_FILE bash script approach
with atomic writes and structured deserialization.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

from ...domain.entities.pull_request import PullRequest
from ...domain.entities.review_item import ReviewItem
from ...domain.value_objects.pull_request_id import PullRequestId
from ...domain.value_objects.commit_sha import CommitSha
from ...domain.value_objects.code_review import CodeReview
from ...domain.value_objects.review_verdict import ReviewVerdict
from ...domain.value_objects.item_severity import ItemSeverity
from ...domain.value_objects.issue_category import IssueCategory
from ...domain.value_objects.comment_id import CommentId
from ...application.ports.outbound.pull_request_repository import (
    PullRequestRepository,
)

_STATE_KEY_SEPARATOR = "/"


class JsonFilePullRequestRepository(PullRequestRepository):
    """Serialize and deserialize the PullRequest aggregate to a local JSON file.

    Atomic writes: writes to a .tmp sibling file, then os.replace() to avoid
    partial writes on crash.
    """

    def __init__(self, file_path: str | Path) -> None:
        self._file_path = Path(file_path)

    # ── port methods ────────────────────────────────────────────────

    def find(self, pr_id: PullRequestId) -> PullRequest | None:
        data = self._load()
        reviewed = data.get("reviewed", {})

        key = _make_key(pr_id)
        raw = reviewed.get(key)
        if raw is None:
            logger.debug("No persisted state for %s", pr_id)
            return None

        logger.debug("Found persisted state for %s", pr_id)
        pr = self._deserialize(pr_id, raw)
        logger.info(
            "JsonFilePullRequestRepository.find return: title='%s' sha=%s reviews=%d",
            pr.title, pr.head_sha.value[:7], len(pr.reviews),
        )
        return pr

    def save(self, pr: PullRequest) -> None:
        logger.info("Persisting state for %s (%d reviews)", pr.id, len(pr.reviews))
        data = self._load()
        reviewed = data.setdefault("reviewed", {})

        key = _make_key(pr.id)
        reviewed[key] = self._serialize(pr)

        self._save(data)

    def reset(self) -> None:
        """Clear all persisted state by deleting and recreating the file."""
        logger.info("Resetting state file %s", self._file_path)
        if self._file_path.exists():
            self._file_path.unlink()
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_path.write_text('{"reviewed":{}}')

    # ── private ─────────────────────────────────────────────────────

    def _load(self) -> dict:
        if not self._file_path.exists():
            return {"reviewed": {}}
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            from ...domain.exceptions import RepositoryCorruptedError
            raise RepositoryCorruptedError(
                f"State file {self._file_path} is corrupted or unreadable"
            ) from exc

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

    # ── serialization ───────────────────────────────────────────────

    def _serialize(self, pr: PullRequest) -> dict:
        return {
            "title": pr.title,
            "head_sha": str(pr.head_sha),
            "is_draft": pr.is_draft,
            "reviews": [
                {
                    "verdict": r.verdict.value,
                    "summary": r.summary,
                    "model_used": r.model_used,
                    "items": [
                        {
                            "number": i.number,
                            "severity": i.severity.value,
                            "category": i.category.value,
                            "file_path": i.file_path,
                            "description": i.description,
                        }
                        for i in r.items
                    ],
                }
                for r in pr.reviews
            ],
            "processed_comment_ids": sorted(
                str(c) for c in pr.processed_comment_ids
            ),
        }

    def _deserialize(self, pr_id: PullRequestId, raw: dict) -> PullRequest:
        reviews_raw = raw.get("reviews", [])
        reviews: tuple[CodeReview, ...] = tuple(
            CodeReview(
                verdict=ReviewVerdict(r["verdict"]),
                summary=r.get("summary", ""),
                model_used=r.get("model_used", ""),
                items=[
                    ReviewItem(
                        number=i["number"],
                        severity=ItemSeverity.from_value(i.get("severity")),
                        category=IssueCategory.from_value(i.get("category")),
                        file_path=i.get("file_path"),
                        description=i.get("description", ""),
                    )
                    for i in r.get("items", [])
                ],
            )
            for r in reviews_raw
        )

        processed_ids: frozenset[CommentId] = frozenset(
            CommentId(str(cid))
            for cid in raw.get("processed_comment_ids", [])
        )

        return PullRequest(
            id=pr_id,
            title=raw.get("title", ""),
            head_sha=CommitSha(raw.get("head_sha", "")),
            is_draft=raw.get("is_draft", False),
            reviews=reviews,
            processed_comment_ids=processed_ids,
        )


def _make_key(pr_id: PullRequestId) -> str:
    return f"{pr_id.repository}{_STATE_KEY_SEPARATOR}{pr_id.number}"
