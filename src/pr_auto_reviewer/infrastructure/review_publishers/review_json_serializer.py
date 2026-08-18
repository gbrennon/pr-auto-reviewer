"""ReviewJsonSerializer — JSON serialization of a CodeReview for terminal output."""

import json

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.entities.review_praise import ReviewPraise
from pr_auto_reviewer.domain.entities.review_suggestion import ReviewSuggestion
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview


class ReviewJsonSerializer:
    """Serialize a ``CodeReview`` into a compact JSON document.

    Empty or ``None`` field values are omitted so serialized output stays
    clean and free of default placeholders.
    """

    def serialize(self, review: CodeReview) -> str:
        """Return the JSON serialization of *review*."""
        data = {
            "verdict": review.verdict.value,
            "reason": review.reason,
            "summary": review.summary,
            "items": [self._convert(item) for item in review.items],
            "suggestions": [self._convert(item) for item in review.suggestions],
            "praise": [self._convert(item) for item in review.praise],
            "model_used": review.model_used,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _compact(
        self, payload: dict[str, object],
    ) -> dict[str, object]:
        """Drop keys whose value is empty to keep output free of defaults."""
        return {
            key: value
            for key, value in payload.items()
            if value not in ("", None)
        }

    def _convert(self, item: object) -> object:
        """Shape a review artifact into its JSON-safe dictionary form."""
        if isinstance(item, ReviewItem):
            return self._compact({
                "severity": item.severity.value,
                "category": item.category.value,
                "file_path": item.file_path,
                "description": item.description,
                "line": item.line,
                "id": item.id,
                "current_code": item.current_code,
                "suggested_fix": item.suggested_fix,
            })
        if isinstance(item, ReviewSuggestion):
            return self._compact({
                "file": item.file,
                "line": item.line,
                "description": item.description,
                "current_code": item.current_code,
                "suggested_code": item.suggested_code,
            })
        if isinstance(item, ReviewPraise):
            return self._compact({
                "file": item.file,
                "description": item.description,
            })
        return item