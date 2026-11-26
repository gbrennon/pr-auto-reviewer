"""JsonFilePullRequestRepository — persistence adapter for PullRequest aggregate.

Implements PullRequestRepositoryPort. Replaces the STATE_FILE bash script approach
with atomic writes and structured deserialization.
"""

from __future__ import annotations

from ...domain.entities.review_item import ReviewItem
from ...domain.exceptions import RepositoryCorruptedError
from ...domain.value_objects.code_review import CodeReview
from ...domain.value_objects.review_verdict import ReviewVerdict
from .review_item_codec import ReviewItemCodec


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
        try:
            if not isinstance(raw, dict):
                raise ValueError("review payload must be an object")
            verdict = cls._resolve_verdict(raw["verdict"])
            reason = cls._required_text(raw, "reason")
            summary = cls._required_text(raw, "summary")
            model_used = cls._required_text(raw, "model_used")
            items = cls._deserialize_collection(raw, "items")
            suggestions = cls._deserialize_collection(raw, "suggestions")
            praise = cls._deserialize_collection(raw, "praise")
            return CodeReview(
                verdict=verdict,
                reason=reason,
                summary=summary,
                model_used=model_used,
                items=items,
                suggestions=suggestions,
                praise=praise,
            )
        except RepositoryCorruptedError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise RepositoryCorruptedError(
                f"Persisted review is malformed: {exc}"
            ) from exc

    @staticmethod
    def _required_text(raw: dict, field: str) -> str:
        value = raw[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        return value

    @staticmethod
    def _resolve_verdict(raw_verdict: object) -> ReviewVerdict:
        if not isinstance(raw_verdict, str) or not raw_verdict.strip():
            raise ValueError("verdict must be a non-empty string")
        try:
            verdict = ReviewVerdict(raw_verdict.strip().lower())
        except ValueError as exc:
            raise ValueError(f"unknown verdict: {raw_verdict}") from exc
        if verdict is ReviewVerdict.COMMENTED:
            raise ValueError("commented is not a persisted review verdict")
        return verdict

    @staticmethod
    def _deserialize_collection(
        raw: dict, field: str
    ) -> list[ReviewItem]:
        collection = raw[field]
        if not isinstance(collection, list):
            raise ValueError(f"{field} must be a list")
        return [ReviewItemCodec.deserialize(item) for item in collection]
