"""JsonFilePullRequestRepository — persistence adapter for PullRequest aggregate.

Implements PullRequestRepositoryPort. Replaces the STATE_FILE bash script approach
with atomic writes and structured deserialization.
"""

from __future__ import annotations

import logging

from ...domain.entities.review_item import ReviewItem
from ...domain.value_objects.code_review import CodeReview
from ...domain.value_objects.review_verdict import ReviewVerdict
from .review_item_codec import ReviewItemCodec

logger = logging.getLogger(__name__)

_STATE_KEY_SEPARATOR = "/"


class CodeReviewCodec:
    """Serialize and deserialize ``CodeReview`` to and from JSON dicts."""

    @staticmethod
    def serialize(review: CodeReview) -> dict:
        return {
            "verdict": review.verdict.value,
            "summary": review.summary,
            "reason": review.reason,
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

