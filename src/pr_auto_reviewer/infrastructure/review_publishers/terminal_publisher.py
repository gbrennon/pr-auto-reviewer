from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import (
    ReviewPublisherPort,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.entities.review_praise import ReviewPraise
from pr_auto_reviewer.domain.entities.review_suggestion import ReviewSuggestion
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.review_publishers._shared import _body_formatter

logger = logging.getLogger(__name__)

class TerminalReviewPublisherAdapter(ReviewPublisherPort):
    def __init__(self, output_path: str | None = None) -> None:
        self._output_path = output_path

    def _review_to_json(self, review: CodeReview) -> str:
        def _compact(payload: dict[str, object]) -> dict[str, object]:
            return {
                key: value
                for key, value in payload.items()
                if value not in ("", None)
            }

        def _convert(item):
            if isinstance(item, ReviewItem):
                return _compact({
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
                return _compact({
                    "file": item.file, "line": item.line,
                    "description": item.description,
                    "current_code": item.current_code,
                    "suggested_code": item.suggested_code,
                })
            if isinstance(item, ReviewPraise):
                return _compact({
                    "file": item.file, "description": item.description,
                })
            return item

        data = {
            "verdict": review.verdict.value,
            "reason": review.reason,
            "summary": review.summary,
            "items": [_convert(it) for it in review.items],
            "suggestions": [_convert(s) for s in review.suggestions],
            "praise": [_convert(p) for p in review.praise],
            "model_used": review.model_used,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def publish(self, pr_id: PullRequestId, review: CodeReview, diff: PullRequestDiff | None = None) -> None:
        body = _body_formatter.format(review)
        json_text = self._review_to_json(review)

        output_lines = [
            f"\n{'=' * 60}",
            f"  Review for {pr_id}",
            f"{'=' * 60}\n",
            "--- HUMAN-READABLE ---",
            body,
            "\n--- JSON ---\n",
            json_text,
            f"\n{'=' * 60}\n",
        ]
        output = "\n".join(output_lines)

        if self._output_path is None:
            logger.info(
                "Terminal output for PR %s: verdict=%s, items=%d -> stdout",
                pr_id,
                review.verdict.value,
                len(review.items),
            )
            sys.stdout.write(output)
            sys.stdout.flush()
        else:
            dest_path = Path(self._output_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_text(output)
            logger.info("Review written to %s", dest_path)
