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
from ...domain.entities.review_item import ReviewItem
from ...domain.exceptions import RepositoryCorruptedError
from ...domain.value_objects.code_review import CodeReview
from ...domain.value_objects.comment_id import CommentId
from ...domain.value_objects.commit_sha import CommitSha
from ...domain.value_objects.issue_category import IssueCategory
from ...domain.value_objects.item_severity import ItemSeverity
from ...domain.value_objects.pull_request_id import PullRequestId
from ...domain.value_objects.review_verdict import ReviewVerdict

logger = logging.getLogger(__name__)

_STATE_KEY_SEPARATOR = "/"

class StateKey:
    """Build the composite storage key for a pull request."""

    @staticmethod
    def of(pr_id: PullRequestId) -> str:
        return f"{pr_id.repository}{_STATE_KEY_SEPARATOR}{pr_id.number}"


class ReviewItemCodec:
    """Serialize and deserialize ``ReviewItem`` to and from JSON dicts."""

    @staticmethod
    def serialize(item: ReviewItem) -> dict:
        return {
            "id": item.id,
            "severity": item.severity.value,
            "category": item.category.value,
            "file_path": item.file_path,
            "description": item.description,
            "line": item.line,
            "current_code": item.current_code,
            "suggested_fix": item.suggested_fix,
            "root_cause": item.root_cause,
            "reproduction": item.reproduction,
            "acceptance_criteria": item.acceptance_criteria,
            "detection_method": item.detection_method,
            "status": item.status,
        }

    @staticmethod
    def deserialize(raw_item: dict) -> ReviewItem:
        return ReviewItem(
            severity=ItemSeverity.from_value(raw_item.get("severity")),
            category=IssueCategory.from_value(raw_item.get("category")),
            file_path=raw_item.get("file_path"),
            description=raw_item.get("description", ""),
            id=raw_item.get("id", ""),
            line=raw_item.get("line", ""),
            current_code=raw_item.get("current_code", ""),
            suggested_fix=raw_item.get("suggested_fix", ""),
            root_cause=raw_item.get("root_cause", ""),
            reproduction=raw_item.get("reproduction", ""),
            acceptance_criteria=raw_item.get("acceptance_criteria", ""),
            detection_method=raw_item.get("detection_method", ""),
            status=raw_item.get("status", "open"),
        )


class CodeReviewCodec:
    """Serialize and deserialize ``CodeReview`` to and from JSON dicts."""

    @staticmethod
    def serialize(review: CodeReview) -> dict:
        return {
            "verdict": review.verdict.value,
            "summary": review.summary,
            "model_used": review.model_used,
            "items": [ReviewItemCodec.serialize(i) for i in review.items],
            "suggestions": [
                ReviewItemCodec.serialize(s) for s in review.suggestions
            ],
            "praise": [ReviewItemCodec.serialize(p) for p in review.praise],
        }

    @classmethod
    def deserialize(cls, raw: dict) -> CodeReview:
        items = [ReviewItemCodec.deserialize(i) for i in raw.get("items", [])]
        suggestions = [
            ReviewItemCodec.deserialize(s) for s in raw.get("suggestions", [])
        ]
        praise = [ReviewItemCodec.deserialize(p) for p in raw.get("praise", [])]
        verdict = cls._resolve_verdict(str(raw.get("verdict", "")), items)
        summary, reason, model_used = cls._resolve_strings(raw, items)
        return CodeReview(
            verdict=verdict,
            reason=reason,
            summary=summary,
            model_used=model_used,
            items=items,
            suggestions=suggestions,
            praise=praise,
        )

    @staticmethod
    def _resolve_verdict(raw_verdict: str, items: list[ReviewItem]) -> ReviewVerdict:
        verdict = ReviewVerdict(raw_verdict.strip().lower())
        if verdict is ReviewVerdict.COMMENTED:
            return (
                ReviewVerdict.CHANGES_REQUESTED if items else ReviewVerdict.APPROVED
            )
        return verdict

    @staticmethod
    def _resolve_strings(raw: dict, items: list[ReviewItem]) -> tuple[str, str, str]:
        summary = (
            raw.get("summary", "")
            or f"Found {len(items)} issue(s) in persisted review."
        )
        reason = raw.get("reason", "") or summary
        model_used = raw.get("model_used", "") or "unknown"
        return summary, reason, model_used

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
            last_command_checked_at=raw.get("last_command_checked_at"),
        )

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
            "unresolved_blocking_ids": sorted(pr.unresolved_blocking_ids),
            "created_issue_item_ids": sorted(pr.created_issue_item_ids),
            "dismissed_item_ids": sorted(pr.dismissed_item_ids),
            "last_reviewed_at": pr.last_reviewed_at,
            "processed_comment_ids": sorted(
                str(c) for c in pr.processed_comment_ids
            ),
            "last_review_request_event_id": pr.last_review_request_event_id,
            "last_command_checked_at": pr.last_command_checked_at,
        }
